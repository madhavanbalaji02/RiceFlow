"""Verify cache identities, discover bounded inputs, and attest regional reference compatibility."""
import argparse
import gzip
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pysam

from .cohort import validate
from .common import Policy, RunConfig, dump, sha
from .network import BudgetClient, regional_vcf

BASE = 'https://s3.amazonaws.com/3kricegenome/snpseek-dl/3krg-base-filt-core-v0.7/'
VCF = 'https://3kricegenome.s3.amazonaws.com/Nipponbare/B001.snp.vcf.gz'
REF = 'https://rapdb.dna.naro.go.jp/download/archive/irgsp1/IRGSP-1.0_genome.fasta.gz'


def run(out, full_budget=500 * 1024**2, regional_budget=16 * 1024**2,
        cache_dir=None, cache_manifest=None, region='chr01:1000000-1010000'):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Preflight output must be new/empty; historical evidence is immutable')
    out.mkdir(parents=True, exist_ok=True)
    match = re.fullmatch(r'(chr\d{2}):(\d+)-(\d+)', region)
    if not match or not 1 <= int(match[2]) <= int(match[3]) or int(match[3]) - int(match[2]) > 100000:
        raise ValueError('Use a one-based inclusive rice region at most 100001 bases')
    contig, start, end = match[1], int(match[2]), int(match[3])
    previous = json.loads(Path(cache_manifest).read_text()) if cache_manifest else {}
    c = BudgetClient(full_budget, regional_budget)
    m = dict(status='RUNNING', retrieved_utc=datetime.now(timezone.utc).isoformat(), tracks={}, sources=[],
             terms={'url': 'https://registry.opendata.aws/3kricegenome/', 'statement': 'Toronto Statement'},
             subset=dict(cohort='lexicographically first 24 FID/IID; chr1:1-1000000', vcf=region),
             source_processing='CoreSNP already filtered and LD-pruned; downstream QC only')
    try:
        if cache_dir and not cache_manifest:
            raise ValueError('Cache reuse requires its previous source manifest')
        prefix = Path(previous.get('cohort_prefix', str(Path(cache_dir) / 'core'))) if cache_dir else out / 'core'
        for ext in ['fam', 'bim', 'bed']:
            url = BASE + f'core_v0.7.{ext}.gz'
            compressed, raw = Path(str(prefix) + f'.{ext}.gz'), Path(str(prefix) + f'.{ext}')
            if cache_dir:
                old = next(x for x in previous['sources'] if x.get('url') == url)
                if sha(compressed) != old['sha256'] or sha(raw) != old['decompressed_sha256']:
                    raise ValueError(f'Cached {ext} checksum does not match attested source')
                # A full gzip read independently rechecks its CRC without redownloading it.
                with gzip.open(compressed, 'rb') as f:
                    for _ in iter(lambda: f.read(1024 * 1024), b''):
                        pass
            else:
                c.head(url)
                c.fetch(url, dest=compressed)
                with gzip.open(compressed, 'rb') as src, raw.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
            m['sources'].append(dict(url=url, path=str(raw.resolve()), bytes=compressed.stat().st_size,
                                     sha256=sha(compressed), decompressed_sha256=sha(raw),
                                     cache_reused=bool(cache_dir)))
        fam, bim = validate(prefix)
        m['cohort_prefix'] = str(prefix.resolve())
        m['tracks']['cohort'] = dict(status='VERIFIED', samples=len(fam), variants=len(bim),
                                     selected_samples=[r[:2] for r in sorted(fam, key=lambda x: (x[0], x[1]))[:24]],
                                     chromosomes=sorted({r[0] for r in bim}, key=int),
                                     bed_bytes=Path(str(prefix) + '.bed').stat().st_size)
    except Exception as e:
        m['tracks']['cohort'] = dict(status='BLOCKED', error=str(e))
    try:
        readme_url = 'https://3kricegenome.s3.amazonaws.com/README-rice-reference-genomes-used.txt'
        c.fetch(readme_url, dest=out / 'reference-readme.txt')
        for filename in ['README-3kRG-SNPs-Permissive-License.txt', 'README-1st-3kRG-Permissive-License.txt']:
            c.fetch('https://3kricegenome.s3.amazonaws.com/' + filename, dest=out / filename)
        source_metadata = c.head(VCF)
        index_metadata = c.head(VCF + '.tbi')
        vcf_path = out / 'B001.region.vcf'
        meta = regional_vcf(c, VCF, contig, start, end, vcf_path)
        meta.pop('header')
        with pysam.VariantFile(str(vcf_path)) as f:
            if list(f.header.samples) != ['B001']:
                raise ValueError('B001 source sample identity mismatch')
            records = list(f)
            meta.update(samples=list(f.header.samples), contigs={x: f.header.contigs[x].length for x in f.header.contigs},
                        declared_formats=list(f.header.formats),
                        observed_formats=sorted({':'.join(r.format) for r in records}))
        meta.update(status='REFERENCE_PENDING', sha256=sha(vcf_path), path=str(vcf_path.resolve()),
                    region=region, source_url=VCF, source_metadata=source_metadata,
                    index_metadata=index_metadata, source_full_sha256=None)
        m['tracks']['vcf'] = meta
        # Exact file named by the original 3kRG README, on RAP-DB's current official NARO host.
        # This is plain gzip; no remote FASTA index is published at the tested sidecar URLs.
        ref_metadata = c.head(REF)
        publisher = c.fetch(REF + '.md5').decode().strip()
        publisher_md5 = publisher.split()[0]
        if not re.fullmatch('[0-9a-f]{32}', publisher_md5):
            raise ValueError('Malformed publisher MD5 checksum')
        cached_ref = previous.get('reference', {})
        reuse_reference = cached_ref.get('status') == 'VERIFIED_REGIONAL_BASES' and cached_ref.get('url') == REF
        fasta = Path(cached_ref['path']) if reuse_reference else out / 'reference.fa'
        compressed = fasta.parent / 'reference.fa.gz'
        if reuse_reference:
            if sha(compressed) != cached_ref['compressed_sha256'] or sha(fasta) != cached_ref['sha256']:
                raise ValueError('Cached reference checksum mismatch')
            if sha(str(fasta) + '.fai') != cached_ref['fai_sha256']:
                raise ValueError('Cached reference index checksum mismatch')
        else:
            c.fetch(REF, dest=compressed)
        md5 = hashlib.md5(compressed.read_bytes()).hexdigest()  # Publisher check; independent SHA256 also recorded.
        if md5 != publisher_md5:
            raise ValueError('Reference publisher MD5 mismatch')
        if not reuse_reference:
            with gzip.open(compressed, 'rb') as src, fasta.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            pysam.faidx(str(fasta))
        from .vcf import load
        _, rows, _, audit = load(vcf_path, fasta, 'B001', region)
        m['reference'] = dict(status='VERIFIED_REGIONAL_BASES', url=REF, assembly='Os-Nipponbare-Reference-IRGSP-1.0',
                               source_metadata=ref_metadata,
                               retrieved_utc=cached_ref['retrieved_utc'] if reuse_reference else datetime.now(timezone.utc).isoformat(),
                               validated_utc=datetime.now(timezone.utc).isoformat(),
                               compressed_bytes=compressed.stat().st_size, bytes=fasta.stat().st_size, cache_reused=reuse_reference,
                               publisher_md5=publisher_md5, publisher_checksum_url=REF + '.md5',
                               compressed_sha256=sha(compressed), sha256=sha(fasta), path=str(fasta.resolve()),
                               fai_sha256=sha(str(fasta) + '.fai'), contig_aliases={},
                               observed_ref_bases_checked=sum(len(r.ref) for r in rows),
                               identity_evidence='3kRG README names RAP-DB IRGSP-1.0_genome.fasta.gz; current official publisher URL and MD5; exact contig names/lengths and all observed REF alleles validated. Soft masking case ignored for base comparison only.')
        meta.update(status='VERIFIED', reference_records=sum(a['kind'] == 'reference' for a in audit),
                    snp_records=sum(a['kind'] == 'snp' for a in audit),
                    unsupported_records=sum(a['kind'] == 'unsupported' for a in audit),
                    genotype_ploidies=sorted({len(r.samples['B001'].get('GT') or ()) for r in rows}),
                    snp_dp_available=sum(a['kind'] == 'snp' and a['dp'] is not None for a in audit),
                    snp_gq_available=sum(a['kind'] == 'snp' and a['gq'] is not None for a in audit))
    except Exception as e:
        m.setdefault('reference', dict(status='BLOCKED', url=REF, error=str(e)))
        m['tracks'].setdefault('vcf', {})['status'] = 'BLOCKED'
        m['tracks']['vcf']['error'] = str(e)
    m['status'] = 'VERIFIED' if all(x['status'] == 'VERIFIED' for x in m['tracks'].values()) else 'PARTIAL_BLOCKED'
    m['transfer'] = dict(used_bytes=c.used, limits=c.limits, requests=c.requests, request_limit=c.request_limit,
                         scope='This preflight invocation; cache hits transfer zero data bytes')
    m['requests'] = c.evidence
    m['metadata_checksums'] = {p.name: sha(p) for p in out.glob('*.txt')}
    dump(out / 'source-manifest.json', m)
    if m['status'] == 'VERIFIED':
        import yaml
        config = RunConfig(track_label='REAL', cohort=m['cohort_prefix'], vcf=m['tracks']['vcf']['path'],
            reference=m['reference']['path'], expected_sample='B001', vcf_region=region,
            source_manifest=str((out / 'source-manifest.json').resolve()), chrom=1, start=1, end=1000000,
            sample_count=24, policy=Policy()).checked()
        (out / 'run-config.yaml').write_text(yaml.safe_dump(config.model_dump(exclude_none=True), sort_keys=False))
    return m


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='data/preflight-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    p.add_argument('--cache-dir')
    p.add_argument('--cache-manifest')
    p.add_argument('--region', default='chr01:1000000-1010000')
    p.add_argument('--full-budget-mib', type=int, default=500)
    p.add_argument('--regional-budget-mib', type=int, default=16)
    a = p.parse_args()
    m = run(a.out, a.full_budget_mib * 1024**2, a.regional_budget_mib * 1024**2,
            a.cache_dir, a.cache_manifest, a.region)
    print(json.dumps(m, indent=2))
    return 0 if m['status'] == 'VERIFIED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
