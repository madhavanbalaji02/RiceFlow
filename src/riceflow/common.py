import hashlib
import json
import os
import tempfile
import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field


class Policy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sample_call_rate: float = Field(default=0.8, ge=0, le=1)
    site_call_rate: float = Field(default=0.9, ge=0, le=1)
    min_dp: int | None = Field(default=5, ge=0)
    min_gq: int | None = Field(default=None, ge=0)
    missing_quality: str = Field(default='not_assessed', pattern='^(not_assessed|fail|error)$')
    min_maf: float = Field(default=0, ge=0, le=0.5)


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n'
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.' + path.name, delete=False) as f:
        temporary = Path(f.name)
        try:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def command(args, log=None):
    p = subprocess.run([str(a) for a in args], text=True, capture_output=True, timeout=1800)
    if log:
        Path(log).write_text('$ ' + ' '.join(map(str, args)) + '\n' + p.stdout + p.stderr)
    if p.returncode:
        raise RuntimeError(f'Command failed ({p.returncode}): {args}\n{p.stderr[-4000:]}')
    return p.stdout


def table(path, rows):
    import csv
    path = Path(path)
    # Explicit sentinel column for empty tables; JSON contains the typed empty list.
    fields = list(rows[0]) if rows else ['empty']
    with path.with_suffix('.tsv').open('w') as f:
        w = csv.DictWriter(f, fields, delimiter='\t')
        w.writeheader()
        w.writerows(rows)
    pq.write_table(pa.Table.from_pylist(rows) if rows else pa.table({'empty': pa.array([], pa.bool_())}),
                   path.with_suffix('.parquet'))


def ratio(n, d):
    return n / d if d else None


def genotype(gt):
    if not gt or all(a is None for a in gt):
        return 'missing'
    if any(a is None for a in gt):
        return 'partial'
    return 'complete'


def metrics(samples, sites, calls):
    """Only complete diploid calls contribute alleles and heterozygosity."""
    if len(sites) != len(calls) or any(len(row) != len(samples) for row in calls):
        raise ValueError('Metric matrix dimensions do not match samples/sites')
    if any(len(g) != 2 or any(a not in (0, 1, None) for a in g) for row in calls for g in row):
        raise ValueError('Metrics require biallelic diploid genotypes')
    sm = []
    for j, sample in enumerate(samples):
        gs = [row[j] for row in calls]
        complete = [g for g in gs if genotype(g) == 'complete']
        sm.append(dict(sample=sample, sites=len(gs), complete=len(complete),
                       partial=sum(genotype(g) == 'partial' for g in gs),
                       missing=sum(genotype(g) == 'missing' for g in gs),
                       call_rate=ratio(len(complete), len(gs)),
                       heterozygosity=ratio(sum(g[0] != g[1] for g in complete), len(complete))))
    vm = []
    for key, row in zip(sites, calls, strict=True):
        complete = [g for g in row if genotype(g) == 'complete']
        ac = sum(sum(g) for g in complete)
        an = 2 * len(complete)
        af = ratio(ac, an)
        vm.append(dict(locus=key, samples=len(samples), complete=len(complete),
                       call_rate=ratio(len(complete), len(samples)), allele1_count=ac,
                       allele_number=an, allele1_frequency=af,
                       maf=min(af, 1 - af) if af is not None else None))
    return sm, vm


def filter_matrix(samples, sites, calls, policy):
    baseline = metrics(samples, sites, calls)
    keep = [j for j, s in enumerate(baseline[0])
            if s['call_rate'] is not None and s['call_rate'] >= policy.sample_call_rate]
    kept_samples = [samples[j] for j in keep]
    recalc = [[row[j] for j in keep] for row in calls]
    after = metrics(kept_samples, sites, recalc)
    indices = [i for i, s in enumerate(after[1]) if s['call_rate'] is not None
               and s['call_rate'] >= policy.site_call_rate and s['maf'] is not None
               and s['maf'] >= policy.min_maf]
    final = metrics(kept_samples, [sites[i] for i in indices], [recalc[i] for i in indices])
    return dict(baseline_samples=baseline[0], baseline_sites=baseline[1],
                after_sample_sites=after[1], final_samples=final[0], final_sites=final[1],
                excluded_samples=[dict(sample=s, reason='no_observed_sites' if baseline[0][j]['call_rate'] is None else 'sample_call_rate')
                                  for j, s in enumerate(samples) if j not in keep],
                excluded_sites=[dict(locus=s, reason=site_exclusion_reason(after[1][i], policy))
                                for i, s in enumerate(sites) if i not in indices],
                retained_sample_indices=keep, retained_site_indices=indices)


def site_exclusion_reason(site, policy):
    if site['samples'] == 0:
        return 'no_retained_samples'
    reasons = []
    if site['call_rate'] is None or site['call_rate'] < policy.site_call_rate:
        reasons.append('site_call_rate')
    if site['allele_number'] == 0:
        reasons.append('no_complete_alleles')
    elif site['maf'] < policy.min_maf:
        reasons.append('minor_allele_frequency')
    return ';'.join(reasons) or 'retained'


def save_metrics(out, result):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in result.items():
        if isinstance(rows, list) and (not rows or isinstance(rows[0], dict)):
            table(out / name, rows)
    dump(out / 'summary.json', result)


class RunConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    track_label: str = Field(pattern=r'^(SYNTHETIC|REAL(?:_[A-Z0-9_]+)?)$')
    cohort: str
    vcf: str | None = None
    reference: str | None = None
    expected_sample: str
    vcf_region: str | None = None
    source_manifest: str | None = None
    chrom: int = Field(ge=1, le=12)
    start: int = Field(ge=1)
    end: int = Field(ge=1)
    sample_count: int = Field(ge=1, le=10000)
    policy: Policy
    input_sha256: dict[str, str] | None = None

    def checked(self):
        if self.end < self.start:
            raise ValueError('Interval end must be >= start (one-based inclusive)')
        if bool(self.vcf) != bool(self.reference):
            raise ValueError('VCF and matching reference must be supplied together')
        if self.track_label.startswith('REAL') and not self.source_manifest:
            raise ValueError('Real-data runs require a preflight source manifest')
        return self
