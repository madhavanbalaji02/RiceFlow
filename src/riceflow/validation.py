"""Independent artifact validation and real-source attestation gates."""
import csv
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pysam

from .cohort import read
from .common import metrics, sha


def verify_real_inputs(cfg):
    source = json.loads(Path(cfg['source_manifest']).read_text())
    if source['tracks']['cohort']['status'] != 'VERIFIED':
        raise ValueError('Real cohort has not passed preflight')
    entries = {x.get('url', '').rsplit('.', 2)[-2]: x for x in source['sources']
               if 'decompressed_sha256' in x}
    if set(entries) != {'bed', 'bim', 'fam'}:
        raise ValueError('Preflight must attest all three cohort file identities')
    def actual(key, path):
        return cfg['input_sha256'][key] if path.startswith('s3://') else sha(path)
    for ext, entry in entries.items():
        if actual('cohort.' + ext, cfg['cohort'] + '.' + ext) != entry['decompressed_sha256']:
            raise ValueError('Cohort checksum no longer matches preflight')
    if cfg.get('vcf'):
        meta, ref = source['tracks'].get('vcf', {}), source.get('reference', {})
        if ref.get('status') != 'VERIFIED_REGIONAL_BASES' or ref.get('sha256') != actual('reference', cfg['reference']):
            raise ValueError('Real VCF requires the verified matching reference from preflight')
        if (meta.get('status') != 'VERIFIED' or meta.get('sha256') != actual('vcf', cfg['vcf'])
                or meta.get('samples') != [cfg['expected_sample']] or not meta.get('index_sha256')):
            raise ValueError('Real VCF source identity/sample/index is not attested by preflight')
        if cfg.get('vcf_region') != meta.get('region'):
            raise ValueError('VCF selection does not match the attested preflight region')
    return source


def validate_track(root, kind):
    root = Path(root)
    result = json.loads((root / 'summary.json').read_text())
    if result['status'] == 'BLOCKED':
        return result
    def check_table(name, rows):
        arrow = pq.read_table(root / (name + '.parquet'))
        if arrow.to_pylist() != rows:
            raise ValueError(f'{kind}: {name} Parquet differs from summary')
        if not rows and (arrow.schema.names != ['empty'] or arrow.schema.field('empty').type != pa.bool_()):
            raise ValueError(f'{kind}: {name} empty Parquet schema is invalid')
        with (root / (name + '.tsv')).open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            fields, tsv = reader.fieldnames, list(reader)
        expected_fields = set(rows[0]) if rows else {'empty'}
        if len(tsv) != len(rows) or len(fields or []) != len(expected_fields) or set(fields or []) != expected_fields:
            raise ValueError(f'{kind}: {name} TSV schema/count differs from summary')
        expected = [{k: '' if v is None else str(v) for k, v in row.items()} for row in rows]
        if tsv != expected:
            raise ValueError(f'{kind}: {name} TSV values differ from summary')

    for name, rows in result.items():
        if isinstance(rows, list) and (not rows or isinstance(rows[0], dict)):
            check_table(name, rows)
    if kind == 'cohort':
        fam, bim, calls = read(root / 'unfiltered')
        baseline = metrics([f'{r[0]}/{r[1]}' for r in fam], [r[1] for r in bim], calls)
        if baseline != (result['baseline_samples'], result['baseline_sites']):
            raise ValueError('Cohort baseline metrics differ from native BED')
        if result['status'] == 'PASS':
            fam, bim, calls = read(root / 'filtered')
            final = metrics([f'{r[0]}/{r[1]}' for r in fam], [r[1] for r in bim], calls)
            if final != (result['final_samples'], result['final_sites']):
                raise ValueError('Cohort final metrics differ from native BED')
    else:
        audit = pq.read_table(root / 'audit.parquet').to_pylist()
        check_table('audit', audit)
        if len(audit) != result['observed_records']:
            raise ValueError('VCF audit record accounting mismatch')
        for name, count in result['scope_counts'].items():
            if sum(r['kind'] == name for r in audit) != count:
                raise ValueError('VCF audit scope accounting mismatch')
        for name, count in result['quality_counts'].items():
            if sum(r['quality_status'] == name for r in audit) != count:
                raise ValueError('VCF audit quality accounting mismatch')
        if sum(result['scope_counts'].values()) != result['observed_records']:
            raise ValueError('VCF scope accounting mismatch')
        if sum(result['quality_counts'].values()) != result['observed_records']:
            raise ValueError('VCF quality accounting mismatch')
        for filename, expected in [('reference-records.vcf.gz', result['scope_counts']['reference']),
                                   ('unsupported-records.vcf.gz', result['scope_counts']['unsupported']),
                                   ('masked.vcf.gz', result['observed_biallelic_snp_sites']),
                                   ('filtered.vcf.gz', len(result['final_sites']))]:
            with pysam.VariantFile(str(root / filename)) as f:
                rows = list(f.fetch())  # Requires an operational local index, including empty outputs.
                if len(rows) != expected:
                    raise ValueError(f'{filename} record count differs from metrics')
                if filename in ['masked.vcf.gz', 'filtered.vcf.gz']:
                    names = list(f.header.samples)
                    calculated = metrics(names, [f'{r.contig}:{r.pos}:{r.ref}:{",".join(r.alts)}' for r in rows],
                                         [[r.samples[s].get('GT') for s in names] for r in rows])
                    stage = 'baseline' if filename.startswith('masked') else 'final'
                    if rows and calculated != (result[stage + '_samples'], result[stage + '_sites']):
                        raise ValueError(f'{filename} genotype metrics differ from summary')
    return result
