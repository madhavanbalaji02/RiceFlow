"""Independent comparison; all samples included, complete diploid allele denominator."""
import shutil
import subprocess
import pytest
from riceflow.cohort import CHR_ARGS, read, run
from riceflow.common import Policy, metrics


@pytest.mark.skipif(not shutil.which('plink2'), reason='EXTERNAL: PLINK 2 required (CI installs it)')
def test_plink_counts(tmp_path):
    run('tests/fixtures/tiny', tmp_path, Policy(), chrom=1, start=1, end=3, sample_count=4)
    import csv
    rows = list(csv.DictReader((tmp_path / 'baseline.acount').open(), delimiter='\t'))
    # PLINK BED A1 becomes provisional ALT. Python counts precisely BIM A1.
    assert int(rows[0]['ALT_CTS']) == 3
    assert int(rows[0]['OBS_CT']) == 6
    miss = list(csv.DictReader((tmp_path / 'baseline.vmiss').open(), delimiter='\t'))
    assert float(miss[0]['F_MISS']) == .25
    assert len(list(csv.DictReader((tmp_path / 'final.acount').open(), delimiter='\t'))) == 3


@pytest.mark.skipif(not shutil.which('bcftools'), reason='EXTERNAL: BCFtools required (CI installs it)')
def test_bcftools_conventions():
    import pysam
    import pysam.bcftools
    v = pysam.VariantFile('tests/fixtures/tiny.vcf.gz')
    rows = list(v)
    calls = [[r.samples['S1']['GT']] for r in rows]
    _, sites = metrics(['S1'], [str(r.pos) for r in rows], calls)
    assert sites[1]['allele1_count'] == 1 and sites[1]['allele_number'] == 2
    out = subprocess.check_output(['bcftools', 'query', '-f', '%POS[\t%GT]\n',
                                   'tests/fixtures/tiny.vcf.gz'], text=True)
    assert '6\t0/.\n' in out
    # Independently parse BCFtools' textual GT output; complete calls contribute two alleles.
    for line in out.splitlines():
        pos, gt = line.split('\t')
        alleles = gt.replace('|', '/').split('/')
        expected_an = 0 if '.' in alleles else 2
        expected_ac = 0 if '.' in alleles else sum(int(x) for x in alleles)
        assert sites[int(pos) - 1]['allele_number'] == expected_an
        assert sites[int(pos) - 1]['allele1_count'] == expected_ac
    stats = pysam.bcftools.stats('tests/fixtures/tiny.vcf.gz')
    assert 'number of records:\t9' in stats
    assert 'number of SNPs:\t7' in stats
    # bcftools query preserves a half-call; RiceFlow excludes both alleles from AC/AN for that call.
    assert sites[5]['allele_number'] == 0


def test_rice_diploid_and_no_ref_claim():
    assert CHR_ARGS == ['--chr-set', '12', 'no-x', 'no-y', 'no-xy', 'no-mt']
    fam, bim, calls = read('tests/fixtures/tiny')
    assert bim[0][4:] == ['G', 'A']
    assert calls[0][2] == (1, 1)  # A1/A1 means G/G, independent of reference FASTA A.
