import math
from pathlib import Path

import pysam

from .common import filter_matrix, genotype, metrics, save_metrics, table


def load(vcf, fasta, expected_sample=None, region=None):
    rows, calls, audit, seen = [], [], [], set()
    with pysam.VariantFile(str(vcf)) as f, pysam.FastaFile(str(fasta)) as ref:
        samples = list(f.header.samples)
        if len(samples) != 1 or (expected_sample and samples != [expected_sample]):
            raise ValueError(f'Expected single sample {expected_sample}; found {samples}')
        for c in f.header.contigs:
            if c not in ref.references or f.header.contigs[c].length != ref.get_reference_length(c):
                raise ValueError(f'Incompatible reference contig {c}')
        for r in f:
            if region:
                chrom, interval = region.split(':')
                start, end = map(int, interval.split('-'))
                if r.contig != chrom or not start <= r.pos <= end:
                    raise ValueError(f'VCF record outside configured interval: {r.contig}:{r.pos}')
            if r.contig not in ref.references or ref.fetch(r.contig, r.start, r.start + len(r.ref)).upper() != r.ref.upper():
                raise ValueError(f'Reference mismatch at {r.contig}:{r.pos}')
            key = f'{r.contig}:{r.pos}:{r.ref}:{",".join(r.alts or ["."])}'
            if (r.contig, r.pos) in seen:
                raise ValueError(f'Duplicate/conflicting VCF record {key}')
            seen.add((r.contig, r.pos))
            kind = ('reference' if not r.alts else 'snp' if len(r.ref) == 1 and len(r.alts) == 1
                    and len(r.alts[0]) == 1 and r.ref in 'ACGT' and r.alts[0] in 'ACGT'
                    and r.alts[0] != r.ref else 'unsupported')
            s = r.samples[samples[0]]
            gt = s.get('GT') or (None, None)
            if len(gt) != 2 or any(a is not None and (a < 0 or a > len(r.alts or [])) for a in gt):
                raise ValueError(f'Invalid/non-diploid genotype at {key}')
            audit.append(dict(locus=key, kind=kind,
                              original_gt=('|' if s.phased else '/').join('.' if a is None else str(a) for a in gt),
                              source_filter=';'.join(r.filter) or '.', dp=s.get('DP'), gq=s.get('GQ'),
                              original_state=genotype(gt)))
            rows.append(r.copy())
            calls.append([gt])
    return samples, rows, calls, audit


def assess_quality(a, policy):
    """Assess each required field on this record, independently of its header declaration."""
    failed, unavailable = [], []
    for field, threshold in [('dp', policy.min_dp), ('gq', policy.min_gq)]:
        if threshold is None:
            continue
        if a[field] is None:
            unavailable.append('missing_' + field)
        elif not isinstance(a[field], (int, float)) or not math.isfinite(a[field]) or a[field] < 0:
            raise ValueError(f'Invalid {field} at {a["locus"]}')
        elif a[field] < threshold:
            failed.append('low_' + field)
    if unavailable and policy.missing_quality == 'error':
        raise ValueError(f'Missing quality at {a["locus"]}: {unavailable}')
    if unavailable and policy.missing_quality == 'fail':
        failed.extend(unavailable)
    status = 'failed' if failed else 'not_assessed' if unavailable else 'passed'
    return status, ';'.join(dict.fromkeys(failed + unavailable)) or 'none'


def run(vcf, fasta, out, policy, expected_sample=None, region=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    samples, records, calls, audit = load(vcf, fasta, expected_sample, region)
    supported, masked, keys = [], [], []
    for i, a in enumerate(audit):
        if a['kind'] != 'snp':
            a.update(quality_status='scope_exclusion', reasons=a['kind'])
            continue
        status, reasons = assess_quality(a, policy)
        # Not assessed calls are masked conservatively, separately from measured quality failures.
        gt = calls[i][0] if status == 'passed' else (None, None)
        a.update(quality_status=status, reasons=reasons)
        supported.append(i)
        keys.append(a['locus'])
        masked.append([gt])
    result = filter_matrix(samples, keys, masked, policy)
    result['original_samples'], result['original_sites'] = metrics(samples, keys, [calls[i] for i in supported])
    result['region'] = region
    result['observed_records'] = len(records)
    result['observed_biallelic_snp_sites'] = len(supported)
    result['scope_exclusions'] = len(records) - len(supported)
    result['scope_counts'] = {kind: sum(a['kind'] == kind for a in audit) for kind in ['reference', 'unsupported', 'snp']}
    result['quality_counts'] = {s: sum(a['quality_status'] == s for a in audit)
                                for s in ['failed', 'not_assessed', 'passed', 'scope_exclusion']}
    result['quality_availability'] = {kind: {field: sum(a['kind'] == kind and a[field] is not None for a in audit)
                                           for field in ['dp', 'gq']} for kind in ['reference', 'snp', 'unsupported']}
    result['status'] = 'PASS' if result['retained_sample_indices'] and result['retained_site_indices'] else 'EMPTY'
    result['interpretation'] = ('Observed regional SNP records only. Absent positions are unknown, never 0/0. '
                                'Baseline/final use different site denominators; retained completeness is selection, not improved accuracy.')
    keep = set(result['retained_site_indices'])
    exclusions = {x['locus']: x['reason'] for x in result['excluded_sites']}
    for a in audit:
        a['retained'] = a['kind'] == 'snp' and a['locus'] not in exclusions
        a['site_decision'] = exclusions.get(a['locus'], 'retained') if a['kind'] == 'snp' else 'scope_exclusion'
    with pysam.VariantFile(str(vcf)) as src:
        header = src.header.copy()
        header.add_line('##FORMAT=<ID=OGT,Number=1,Type=String,Description="Original genotype">')
        header.add_line('##FORMAT=<ID=QCR,Number=1,Type=String,Description="QC status and reasons">')
        for filename, final in [('masked.vcf.gz', False), ('filtered.vcf.gz', True)]:
            with pysam.VariantFile(str(out / filename), 'wz', header=header) as dst:
                for j, i in enumerate(supported):
                    if final and (j not in keep or not result['retained_sample_indices']):
                        continue
                    r = records[i].copy()
                    r.translate(header)
                    phased = r.samples[samples[0]].phased
                    r.samples[samples[0]]['OGT'] = audit[i]['original_gt']
                    r.samples[samples[0]]['QCR'] = audit[i]['quality_status'] + '|' + audit[i]['reasons']
                    r.samples[samples[0]]['GT'] = masked[j][0]
                    r.samples[samples[0]].phased = phased
                    for tag in ['AC', 'AN', 'AF', 'NS', 'MLEAC', 'MLEAF']:
                        if tag in r.info:
                            del r.info[tag]
                    dst.write(r)
            pysam.tabix_index(str(out / filename), preset='vcf', force=True)
        for kind, filename in [('reference', 'reference-records.vcf.gz'), ('unsupported', 'unsupported-records.vcf.gz')]:
            with pysam.VariantFile(str(out / filename), 'wz', header=src.header) as dst:
                for r, a in zip(records, audit, strict=True):
                    if a['kind'] == kind:
                        dst.write(r)
            pysam.tabix_index(str(out / filename), preset='vcf', force=True)
    table(out / 'audit', audit)
    result['stage_counts'] = dict(observed_records=len(records), eligible_snp_sites=len(supported),
        original_complete_calls=sum(s['complete'] for s in result['original_samples']),
        after_mask_complete_calls=sum(s['complete'] for s in result['baseline_samples']),
        excluded_samples=len(result['excluded_samples']), assessed_sites_after_samples=len(result['after_sample_sites']),
        excluded_sites=len(result['excluded_sites']), retained_sites=len(result['final_sites']))
    result['sensitivity'] = []
    for dp in dict.fromkeys([policy.min_dp, 0, 5, 10, 30]):
        candidate = policy.model_copy(update={'min_dp': dp})
        matrix = [[calls[i][0] if assess_quality(audit[i], candidate)[0] == 'passed' else (None, None)]
                  for i in supported]
        x = filter_matrix(samples, keys, matrix, candidate)
        result['sensitivity'].append(dict(changed_parameter='baseline' if dp == policy.min_dp else 'min_dp',
            min_dp=dp, min_gq=policy.min_gq, missing_quality=policy.missing_quality,
            sample_call_rate=policy.sample_call_rate, site_call_rate=policy.site_call_rate,
            observed_snp_sites=len(supported), retained_sites=len(x['retained_site_indices']),
            retained_samples=len(x['retained_sample_indices'])))
    save_metrics(out, result)
    return result
