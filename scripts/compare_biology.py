"""Semantic comparison; ignore run IDs, headers containing dates and compression metadata."""
import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq
import pysam

from riceflow.common import dump, sha


def canonical_vcf(path):
    with pysam.VariantFile(str(path)) as f:
        return [dict(contig=r.contig, pos=r.pos, ref=r.ref, alts=r.alts, filter=list(r.filter),
                     info=dict(r.info), samples={s: dict(gt=dict(v), phased=v.phased)
                                                for s, v in r.samples.items()}) for r in f.fetch()]


def compare(first, second):
    checks = {}
    for kind in ['cohort', 'vcf']:
        a, b = Path(first) / kind, Path(second) / kind
        checks[kind + '/summary.json'] = json.loads((a / 'summary.json').read_text()) == json.loads((b / 'summary.json').read_text())
        for path in sorted(a.glob('*.parquet')):
            checks[kind + '/' + path.name] = pq.read_table(path).to_pylist() == pq.read_table(b / path.name).to_pylist()
        if kind == 'cohort':
            for prefix in ['unfiltered', 'filtered']:
                for suffix in ['bed', 'bim', 'fam']:
                    name = prefix + '.' + suffix
                    if (a / name).exists():
                        checks[kind + '/' + name] = sha(a / name) == sha(b / name)
        else:
            for path in sorted(a.glob('*.vcf.gz')):
                checks[kind + '/' + path.name] = canonical_vcf(path) == canonical_vcf(b / path.name)
    return dict(equivalent=all(checks.values()), comparisons=checks,
                ignored='Run IDs, execution logs, resource measurements, VCF header command timestamps and compression bytes')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--first', required=True)
    p.add_argument('--second', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    result = compare(a.first, a.second)
    dump(a.out, result)
    print(json.dumps(dict(equivalent=result['equivalent'], comparisons=len(result['comparisons']))))
    raise SystemExit(0 if result['equivalent'] else 1)
