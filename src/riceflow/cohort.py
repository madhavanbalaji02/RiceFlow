"""Native SNP-major BED handling; allele 1 counts never imply ALT counts."""
from pathlib import Path

from .common import command, filter_matrix, save_metrics

DECODE = {0: (1, 1), 1: (None, None), 2: (0, 1), 3: (0, 0)}
ENCODE = {(1, 1): 0, (None, None): 1, (0, 1): 2, (1, 0): 2, (0, 0): 3}
CHR_ARGS = ['--chr-set', '12', 'no-x', 'no-y', 'no-xy', 'no-mt']


def validate(prefix):
    prefix = str(prefix)
    fam = [x.split() for x in Path(prefix + '.fam').read_text().splitlines() if x.strip()]
    if not fam or any(len(r) != 6 for r in fam):
        raise ValueError('FAM must contain nonempty six-field records')
    ids = [(r[0], r[1]) for r in fam]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate sample identities')
    bim = []
    keys, positions = set(), set()
    with open(prefix + '.bim') as f:
        for line in f:
            r = line.split()
            if len(r) != 6:
                raise ValueError('BIM must have six fields')
            chrom, name, cm, pos, a1, a2 = r
            if not chrom.isdigit() or not 1 <= int(chrom) <= 12 or int(pos) < 1:
                raise ValueError(f'Unsupported rice chromosome/position: {r}')
            float(cm)
            if a1 not in 'ACGT' or a2 not in 'ACGT' or len(a1) != 1 or len(a2) != 1 or a1 == a2:
                raise ValueError(f'Unsupported allele: {r}')
            key = f'{chrom}:{pos}:{a1}:{a2}'
            if key in keys or (chrom, pos) in positions:
                raise ValueError(f'Duplicate/conflicting locus: {key}')
            keys.add(key)
            positions.add((chrom, pos))
            bim.append(r)
    nbytes = (len(fam) + 3) // 4
    bed = Path(prefix + '.bed')
    if not bim or bed.stat().st_size != 3 + len(bim) * nbytes:
        raise ValueError('BED dimensions do not match BIM/FAM')
    with bed.open('rb') as f:
        if f.read(3) != b'\x6c\x1b\x01':
            raise ValueError('BED must be SNP-major PLINK binary')
        for _ in bim:
            block = f.read(nbytes)
            if len(fam) % 4 and block[-1] >> (2 * (len(fam) % 4)):
                raise ValueError('Nonzero BED padding bits')
    return fam, bim


def read(prefix):
    fam, bim = validate(prefix)
    calls = []
    with open(str(prefix) + '.bed', 'rb') as f:
        f.read(3)
        for _ in bim:
            b = f.read((len(fam) + 3) // 4)
            calls.append([DECODE[(b[j // 4] >> (2 * (j % 4))) & 3] for j in range(len(fam))])
    return fam, bim, calls


def write(prefix, fam, bim, calls):
    for suffix, rows in [('fam', fam), ('bim', bim)]:
        Path(str(prefix) + '.' + suffix).write_text(''.join('\t'.join(r) + '\n' for r in rows))
    with open(str(prefix) + '.bed', 'wb') as f:
        f.write(b'\x6c\x1b\x01')
        for row in calls:
            b = bytearray((len(fam) + 3) // 4)
            for j, gt in enumerate(row):
                b[j // 4] |= ENCODE[tuple(gt)] << (2 * (j % 4))
            f.write(b)


def run(prefix, out, policy, chrom=1, start=1, end=1000000, sample_count=24, plink='plink2'):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    fam, bim = validate(prefix)
    chosen = sorted(fam, key=lambda r: (r[0], r[1]))[:sample_count]
    keepfile = out / 'selected.samples'
    keepfile.write_text(''.join(f'{r[0]}\t{r[1]}\n' for r in chosen))
    common = [plink, *CHR_ARGS, '--threads', '1', '--memory', '1024']
    subset = out / 'unfiltered'
    command([*common, '--bfile', prefix, '--keep', keepfile, '--chr', chrom,
             '--from-bp', start, '--to-bp', end, '--make-bed', '--out', subset], out / 'subset.log')
    fam, bim, calls = read(subset)
    # Unique IDs independent of potentially repeated original IDs; preserve the map.
    (out / 'variant_ids.tsv').write_text('locus\toriginal_id\n' + ''.join(
        f'{r[0]}:{r[3]}:{r[4]}:{r[5]}\t{r[1]}\n' for r in bim))
    for r in bim:
        r[1] = f'{r[0]}:{r[3]}:{r[4]}:{r[5]}'
    write(subset, fam, bim, calls)
    samples = [f'{r[0]}/{r[1]}' for r in fam]
    result = filter_matrix(samples, [r[1] for r in bim], calls, policy)
    result['selection'] = dict(chrom=chrom, start=start, end=end, samples=samples)
    result['allele_orientation'] = 'allele1 is BIM A1; neither A1 nor A2 is independently reference-validated'
    for tag, p in [('baseline', subset)]:
        command([*common, '--bfile', p, '--nonfounders', '--missing', '--freq', 'counts',
                 '--out', out / tag], out / f'{tag}.command.log')
    js, ix = result['retained_sample_indices'], result['retained_site_indices']
    result['status'] = 'PASS' if js and ix else 'EMPTY'
    if js and ix:
        filtered = out / 'filtered'
        write(filtered, [fam[j] for j in js], [bim[i] for i in ix], [[calls[i][j] for j in js] for i in ix])
        command([*common, '--bfile', filtered, '--nonfounders', '--missing', '--freq', 'counts',
                 '--out', out / 'final'], out / 'final.command.log')
    result['sensitivity'] = [dict(sample_call_rate=s, site_call_rate=t,
                                retained_samples=len(x['retained_sample_indices']),
                                retained_sites=len(x['retained_site_indices']))
                             for s, t in [(0.7, 0.8), (0.8, 0.9), (0.95, 0.98)]
                             for x in [filter_matrix(samples, [r[1] for r in bim], calls,
                                                     policy.model_copy(update={'sample_call_rate': s,
                                                                               'site_call_rate': t}))]]
    save_metrics(out, result)
    return result
