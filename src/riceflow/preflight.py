import gzip
import json
from pathlib import Path

import pysam

from .cohort import validate
from .common import dump, sha
from .network import BudgetClient, regional_vcf

BASE = 'https://s3.amazonaws.com/3kricegenome/snpseek-dl/3krg-base-filt-core-v0.7/'
VCF = 'https://3kricegenome.s3.amazonaws.com/Nipponbare/B001.snp.vcf.gz'
REF = 'https://rapdb.dna.affrc.go.jp/download/archive/irgsp1/IRGSP-1.0_genome.fasta.gz'


def run(out, full_budget=500 * 1024**2, regional_budget=16 * 1024**2):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    c = BudgetClient(full_budget, regional_budget)
    m = dict(status='RUNNING', tracks={}, sources=[],
             terms={'url': 'https://registry.opendata.aws/3kricegenome/',
                    'statement': 'Toronto Statement; cite 3kRG and source publications; not a blanket software license'},
             subset=dict(cohort='lexicographically first 24 FID/IID; chr1:1-1000000',
                         vcf='B001 chr01:10000-11000, one-based inclusive'),
             source_processing='CoreSNP already filtered and LD-pruned; downstream QC only')
    try:
        for filename in ['README-3kRG-SNPs-Permissive-License.txt', 'README-1st-3kRG-Permissive-License.txt']:
            url = 'https://3kricegenome.s3.amazonaws.com/' + filename
            c.fetch(url, dest=out / filename)
            m['sources'].append(dict(url=url, sha256=sha(out / filename)))
        for ext in ['fam', 'bim', 'bed']:
            url = BASE + f'core_v0.7.{ext}.gz'
            compressed = out / f'core.{ext}.gz'
            c.fetch(url, dest=compressed)
            with gzip.open(compressed, 'rb') as src, open(out / f'core.{ext}', 'wb') as dst:
                import shutil
                shutil.copyfileobj(src, dst)
            m['sources'].append(dict(url=url, bytes=compressed.stat().st_size, sha256=sha(compressed),
                                     decompressed_sha256=sha(out / f'core.{ext}')))
        c.fetch(BASE + 'readme_core_v0.7.txt', dest=out / 'cohort-readme.txt')
        fam, bim = validate(out / 'core')
        m['tracks']['cohort'] = dict(status='VERIFIED', samples=len(fam), variants=len(bim),
                                     chromosomes=sorted({r[0] for r in bim}, key=int),
                                     duplicate_variant_ids=len(bim) - len({r[1] for r in bim}),
                                     bed_bytes=(out / 'core.bed').stat().st_size,
                                     sample_ids_sha256=sha(out / 'core.fam'))
    except Exception as e:
        m['tracks']['cohort'] = dict(status='BLOCKED', error=str(e))
    try:
        c.fetch('https://3kricegenome.s3.amazonaws.com/README-rice-reference-genomes-used.txt',
                dest=out / 'reference-readme.txt')
        meta = regional_vcf(c, VCF, 'chr01', 10000, 11000, out / 'B001.region.vcf')
        with pysam.VariantFile(str(out / 'B001.region.vcf')) as f:
            if list(f.header.samples) != ['B001']:
                raise ValueError('B001 URL does not contain the expected B001 sample')
            records = list(f)
            meta.update(samples=list(f.header.samples), contigs={x: f.header.contigs[x].length
                        for x in f.header.contigs}, declared_formats=list(f.header.formats),
                        observed_formats=sorted({':'.join(r.format) for r in records}),
                        reference_records=sum(r.alts is None for r in records),
                        snp_records=sum(r.alts is not None for r in records),
                        genotype_ploidies=sorted({len(s.get('GT') or ()) for r in records for s in r.samples.values()}))
        meta.pop('header')
        meta.update(status='REGION_RETRIEVED_REFERENCE_PENDING', sha256=sha(out / 'B001.region.vcf'),
                    source_url=VCF, source_full_sha256=None)
        m['tracks']['vcf'] = meta
        # Authoritative source identity is from the project's README, not chromosome length alone.
        c.fetch(REF, dest=out / 'reference.fa.gz')
        with gzip.open(out / 'reference.fa.gz', 'rb') as f, open(out / 'reference.fa', 'wb') as d:
            import shutil
            shutil.copyfileobj(f, d)
        pysam.faidx(str(out / 'reference.fa'))
        from .vcf import load
        load(out / 'B001.region.vcf', out / 'reference.fa', meta['samples'][0])
        m['reference'] = dict(status='VERIFIED_REGIONAL_BASES', url=REF, assembly='IRGSP-1.0',
                               compressed_sha256=sha(out / 'reference.fa.gz'), sha256=sha(out / 'reference.fa'),
                               identity_evidence='Official 3kRG README names RAP-DB IRGSP-1.0; all declared contig lengths and observed REF bases checked')
        m['tracks']['vcf']['status'] = 'VERIFIED'
    except Exception as e:
        m['reference'] = dict(status='BLOCKED', url=REF, error=str(e))
        m['tracks'].setdefault('vcf', dict(status='BLOCKED', error=str(e)))
    m['status'] = 'VERIFIED' if all(x['status'] == 'VERIFIED' for x in m['tracks'].values()) else 'PARTIAL_BLOCKED'
    m['transfer'] = dict(used_bytes=c.used, limits=c.limits, requests=c.requests, request_limit=c.request_limit)
    m['requests'] = c.evidence
    for p in out.iterdir():
        if p.is_file() and p.name.endswith('readme.txt'):
            m['sources'].append(dict(path=p.name, sha256=sha(p)))
    dump(out / 'source-manifest.json', m)
    return m


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='data/real')
    p.add_argument('--full-budget-mib', type=int, default=500)
    p.add_argument('--regional-budget-mib', type=int, default=16)
    a = p.parse_args()
    m = run(a.out, a.full_budget_mib * 1024**2, a.regional_budget_mib * 1024**2)
    print(json.dumps(m, indent=2))
    return 0 if m['status'] == 'VERIFIED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
