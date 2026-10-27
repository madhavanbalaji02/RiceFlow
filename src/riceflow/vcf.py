from pathlib import Path

import pysam

from .common import filter_matrix, genotype, save_metrics, table


def load(vcf, fasta, expected_sample=None):
    rows, calls, audit, seen = [], [], [], set()
    with pysam.VariantFile(str(vcf)) as f, pysam.FastaFile(str(fasta)) as ref:
        samples = list(f.header.samples)
        if len(samples) != 1 or (expected_sample and samples != [expected_sample]):
            raise ValueError(f'Expected single sample {expected_sample}; found {samples}')
        for c in f.header.contigs:
            if c not in ref.references or f.header.contigs[c].length != ref.get_reference_length(c):
                raise ValueError(f'Incompatible reference contig {c}')
        for r in f:
            if r.contig not in ref.references or ref.fetch(r.contig, r.start, r.start + len(r.ref)).upper() != r.ref:
                raise ValueError(f'Reference mismatch at {r.contig}:{r.pos}')
            key = f'{r.contig}:{r.pos}:{r.ref}:{",".join(r.alts or ["."])}'
            if (r.contig, r.pos) in seen:
                raise ValueError(f'Duplicate/conflicting VCF record {key}')
            seen.add((r.contig, r.pos))
            kind = ('reference' if not r.alts else 'snp' if len(r.ref) == 1 and len(r.alts) == 1
                    and len(r.alts[0]) == 1 and r.ref in 'ACGT' and r.alts[0] in 'ACGT' else 'unsupported')
            s = r.samples[samples[0]]
            gt = s.get('GT') or (None, None)
            if len(gt) != 2 or any(a is not None and (a < 0 or a > len(r.alts or [])) for a in gt):
                raise ValueError(f'Invalid/non-diploid genotype at {key}')
            audit.append(dict(locus=key, kind=kind, original_gt=('|' if s.phased else '/').join('.' if a is None else str(a) for a in gt),
                              source_filter=';'.join(r.filter) or '.', dp=s.get('DP'), gq=s.get('GQ'),
                              original_state=genotype(gt)))
            rows.append(r.copy())
            calls.append([gt])
    return samples, rows, calls, audit


def run(vcf, fasta, out, policy, expected_sample=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    samples, records, calls, audit = load(vcf, fasta, expected_sample)
    supported, masked, keys = [], [], []
    for i, a in enumerate(audit):
        failed, unavailable = [], []
        if a['kind'] != 'snp':
            a.update(quality_status='scope_exclusion', reasons=a['kind'])
            continue
        for field, threshold in [('dp', policy.min_dp), ('gq', policy.min_gq)]:
            if threshold is None:
                continue
            if a[field] is None:
                unavailable.append('missing_' + field)
            elif a[field] < threshold:
                failed.append('low_' + field)
        if unavailable and policy.missing_quality == 'error':
            raise ValueError(f'Missing quality at {a["locus"]}: {unavailable}')
        if unavailable and policy.missing_quality == 'fail':
            failed.extend(unavailable)
        status = 'failed' if failed else 'not_assessed' if unavailable else 'passed'
        # Not assessed calls are masked conservatively, but counted separately from failed quality.
        gt = calls[i][0] if status == 'passed' else (None, None)
        a.update(quality_status=status, reasons=';'.join(failed + unavailable) or 'none')
        supported.append(i)
        keys.append(a['locus'])
        masked.append([gt])
    result = filter_matrix(samples, keys, masked, policy)
    from .common import metrics
    original = metrics(samples, keys, [calls[i] for i in supported])
    result['original_samples'], result['original_sites'] = original
    result['observed_records'] = len(records)
    result['observed_biallelic_snp_sites'] = len(supported)
    result['scope_exclusions'] = len(records) - len(supported)
    result['quality_counts'] = {s: sum(a['quality_status'] == s for a in audit)
                                for s in ['failed', 'not_assessed', 'passed', 'scope_exclusion']}
    result['status'] = 'PASS' if result['retained_sample_indices'] and result['retained_site_indices'] else 'EMPTY'
    result['interpretation'] = 'Observed regional SNP records only; absent positions are unknown, never 0/0.'
    keep = set(result['retained_site_indices'])
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
                    r.samples[samples[0]]['OGT'] = audit[i]['original_gt']
                    r.samples[samples[0]]['QCR'] = audit[i]['quality_status'] + '|' + audit[i]['reasons']
                    r.samples[samples[0]]['GT'] = masked[j][0]
                    # INFO counts may describe source calls; do not leave stale summaries after masking.
                    for tag in ['AC', 'AN', 'AF', 'NS']:
                        if tag in r.info:
                            del r.info[tag]
                    dst.write(r)
            pysam.tabix_index(str(out / filename), preset='vcf', force=True)
    table(out / 'audit', audit)
    result['sensitivity'] = []
    for dp in [0, 5, 10]:
        candidate = []
        for i in supported:
            a = audit[i]
            ok = a['dp'] is not None and a['dp'] >= dp
            if policy.min_gq is not None:
                ok = ok and a['gq'] is not None and a['gq'] >= policy.min_gq
            candidate.append([calls[i][0] if ok else (None, None)])
        x = filter_matrix(samples, keys, candidate, policy)
        result['sensitivity'].append(dict(min_dp=dp, retained_sites=len(x['retained_site_indices']),
                                          retained_samples=len(x['retained_sample_indices'])))
    save_metrics(out, result)
    return result
