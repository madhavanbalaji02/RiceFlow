"""Compare hand-inspectable real records via standalone-tool textual outputs."""
import argparse
import csv
import json
import subprocess
from pathlib import Path

from riceflow.common import dump

p = argparse.ArgumentParser()
p.add_argument('--run', required=True)
p.add_argument('--source', required=True)
p.add_argument('--out', required=True)
a = p.parse_args()
root = Path(a.run)
cmd = ['bcftools', 'query', '-f', '%CHROM\t%POS\t%REF\t%ALT\t%FILTER[\t%GT\t%DP\t%GQ]\n']
raw = subprocess.check_output([*cmd, a.source], text=True)
original = [dict(zip(['contig', 'pos', 'ref', 'alt', 'filter', 'gt', 'dp', 'gq'], row.split('\t'), strict=True))
            for row in raw.splitlines()]
snps = [r for r in original if r['alt'] != '.' and len(r['ref']) == len(r['alt']) == 1 and r['ref'] != r['alt']]
policy = json.loads((root / 'policy.json').read_text())
assessed = []
for r in snps:
    failed, unassessed = False, False
    for field in ['dp', 'gq']:
        cutoff = policy['min_' + field]
        if cutoff is not None:
            if r[field] == '.':
                unassessed = True
            else:
                failed |= int(r[field]) < cutoff
    r['decision'] = 'failed' if failed else 'not_assessed' if unassessed else 'passed'
    assessed.append(r)
q = json.loads((root / 'vcf/summary.json').read_text())
assert len(original) == q['observed_records']
assert len(snps) == q['observed_biallelic_snp_sites']
def complete(r):
    return '.' not in r['gt'] and len(r['gt'].replace('|', '/').split('/')) == 2

n = sum(r['decision'] == 'passed' and complete(r) for r in assessed)
assert n == q['baseline_samples'][0]['complete']
assert q['baseline_samples'][0]['call_rate'] == n / len(snps)
masked = subprocess.check_output([*cmd, str(root / 'vcf/masked.vcf.gz')], text=True)
for line, original_row in zip(masked.splitlines(), assessed, strict=True):
    r = dict(zip(['contig', 'pos', 'ref', 'alt', 'filter', 'gt', 'dp', 'gq'], line.split('\t'), strict=True))
    assert r['filter'] == original_row['filter']
    assert r['gt'] == (original_row['gt'] if original_row['decision'] == 'passed' else './.')
    metric = next(x for x in q['baseline_sites'] if x['locus'].split(':')[1] == r['pos'])
    alleles = r['gt'].replace('|', '/').split('/')
    assert metric['allele_number'] == (0 if '.' in alleles else 2)
    assert metric['allele1_count'] == (0 if '.' in alleles else sum(map(int, alleles)))
cohort = json.loads((root / 'cohort/summary.json').read_text())
for stage, metric in [('baseline', 'baseline_sites'), ('final', 'final_sites')]:
    with (root / f'cohort/{stage}.acount').open() as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    assert len(rows) == len(cohort[metric])
    for r, m in zip(rows, cohort[metric], strict=True):
        assert r['ID'] == m['locus']
        assert int(r['ALT_CTS']) == m['allele1_count']
        assert int(r['OBS_CT']) == m['allele_number']
dump(a.out, dict(verified=True, source_command=[*cmd, a.source], supported_records=assessed,
                 observed_records=len(original), observed_snp_denominator=len(snps),
                 complete_after_mask=n, call_rate_after_mask=n / len(snps),
                 cohort_plink_baseline_rows=len(cohort['baseline_sites']),
                 cohort_plink_final_rows=len(cohort['final_sites']),
                 conventions='BCFtools GT text counted independently; half-calls contribute no alleles. PLINK provisional ALT is BED A1, not validated reference orientation.'))
print(a.out)
