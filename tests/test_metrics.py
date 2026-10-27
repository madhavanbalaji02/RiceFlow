import pytest
from riceflow.common import Policy, filter_matrix, genotype, metrics
from riceflow.cohort import read, validate
from riceflow.vcf import load, run


def test_states_and_zero_denominators():
    assert [genotype(g) for g in [(0, 0), (0, 1), (1, 1), (None, None), (0, None)]] == [
        'complete', 'complete', 'complete', 'missing', 'partial']
    s, v = metrics(['a'], ['x'], [[(0, None)]])
    assert s[0]['call_rate'] == 0
    assert s[0]['heterozygosity'] is None
    assert v[0]['allele1_frequency'] is None
    assert metrics(['a'], [], [])[0][0]['call_rate'] is None
    assert metrics([], ['x'], [[]])[1][0]['call_rate'] is None


def test_hand_calculated_cohort():
    fam, bim, calls = read('tests/fixtures/tiny')
    r = filter_matrix([r[1] for r in fam], [r[1] for r in bim], calls, Policy())
    assert r['baseline_sites'][0]['call_rate'] == .75
    assert r['baseline_sites'][0]['allele1_count'] == 3
    assert r['baseline_sites'][0]['allele1_frequency'] == .5
    assert r['baseline_samples'][1]['heterozygosity'] == .75
    assert r['excluded_samples'] == [dict(sample='D', reason='sample_call_rate')]
    assert r['after_sample_sites'][0]['call_rate'] == 1
    assert len(r['final_sites']) == 4


def test_zero_retained_samples():
    r = filter_matrix(['a'], ['x'], [[(None, None)]], Policy())
    assert r['retained_sample_indices'] == []
    assert r['retained_site_indices'] == []
    assert r['after_sample_sites'][0]['call_rate'] is None


def test_vcf_accounting_and_filter(tmp_path):
    r = run('tests/fixtures/tiny.vcf.gz', 'tests/fixtures/reference.fa', tmp_path,
            Policy(sample_call_rate=.4), 'S1')
    assert r['observed_records'] == 9
    assert r['scope_exclusions'] == 2
    assert r['quality_counts'] == dict(failed=1, not_assessed=1, passed=5, scope_exclusion=2)
    assert r['original_samples'][0]['complete'] == 5
    assert r['baseline_samples'][0]['complete'] == 3
    assert r['baseline_samples'][0]['partial'] == 1
    assert len(r['final_sites']) == 3
    import pysam
    with pysam.VariantFile(str(tmp_path / 'masked.vcf.gz')) as f:
        rows = list(f)
    assert list(rows[1].filter) == ['LowQual']
    assert rows[1].samples['S1']['GT'] == (None, None)
    assert rows[1].samples['S1']['OGT'] == '1/1'


def test_missing_gq_error(tmp_path):
    with pytest.raises(ValueError, match='Missing quality'):
        run('tests/fixtures/tiny.vcf.gz', 'tests/fixtures/reference.fa', tmp_path,
            Policy(min_gq=20, missing_quality='error'))


@pytest.mark.parametrize('change,match', [
    (lambda x: x.replace('chr01', 'chr02'), 'contig'),
    (lambda x: x.replace('chr01\t2\t.\tA', 'chr01\t2\t.\tC'), 'Reference mismatch'),
    (lambda x: x + x.splitlines()[-1] + '\n', 'Duplicate'),
    (lambda x: x.replace('0/1:10:30', '0:10:30'), 'diploid')])
def test_bad_vcf(tmp_path, change, match):
    from pathlib import Path
    p = tmp_path / 'bad.vcf'
    p.write_text(change(Path('tests/fixtures/tiny.vcf').read_text()))
    with pytest.raises(ValueError, match=match):
        load(p, 'tests/fixtures/reference.fa')


def test_cohort_duplicates_and_structure(tmp_path):
    import shutil
    for ext in ['bed', 'bim', 'fam']:
        shutil.copy('tests/fixtures/tiny.' + ext, tmp_path / ('tiny.' + ext))
    # Repeated numeric IDs on different chromosomes are allowed, conflicting coordinates aren't.
    assert len(validate(tmp_path / 'tiny')[1]) == 4
    p = tmp_path / 'tiny.bim'
    p.write_text(p.read_text().replace('2\t1\t0\t1', '1\t1\t0\t1'))
    with pytest.raises(ValueError, match='Duplicate'):
        validate(tmp_path / 'tiny')


def test_absent_quality_header(tmp_path):
    from pathlib import Path
    p = tmp_path / 'header.vcf'
    lines = Path('tests/fixtures/tiny.vcf').read_text().splitlines()
    p.write_text('\n'.join([x for x in lines if not x.startswith('##FORMAT=<ID=GQ')
                            and not (not x.startswith('#') and x.split('\t')[1] == '2')]) + '\n')
    r = run(p, 'tests/fixtures/reference.fa', tmp_path / 'out', Policy(min_gq=20, sample_call_rate=0))
    assert r['quality_counts']['not_assessed'] > 0


def test_empty_vcf(tmp_path):
    from pathlib import Path
    p = tmp_path / 'empty.vcf'
    p.write_text('\n'.join(x for x in Path('tests/fixtures/tiny.vcf').read_text().splitlines()
                            if x.startswith('#')) + '\n')
    r = run(p, 'tests/fixtures/reference.fa', tmp_path / 'out', Policy())
    assert r['status'] == 'EMPTY'


def test_policy_and_interval_validation():
    from riceflow.common import RunConfig
    with pytest.raises(ValueError):
        Policy(sample_call_rate=1.1)
    with pytest.raises(ValueError):
        Policy(unrecognized=5)
    with pytest.raises(ValueError, match='end'):
        RunConfig(track_label='SYNTHETIC', cohort='x', expected_sample='a', chrom=1,
                  start=9, end=2, sample_count=1, policy=Policy()).checked()


def test_failed_launcher_finalizes_without_success(tmp_path):
    from riceflow.cli import finalize
    r = finalize(tmp_path, {'run_id': 'test', 'label': 'SYNTHETIC', 'started': 'test'}, 42, 'forced failure')
    assert r == 1
    assert not (tmp_path / 'SUCCESS.json').exists()
    import json
    m = json.loads((tmp_path / 'failure-manifest.json').read_text())
    assert m['status'] == 'FAILED'
    assert m['returncode'] == 42


@pytest.mark.parametrize('ext,mutate,match', [
    ('bed', lambda b: b'xxx' + b[3:], 'SNP-major'),
    ('bed', lambda b: b[:-1], 'dimensions'),
    ('fam', lambda b: b + b.splitlines(keepends=True)[0], 'Duplicate sample'),
    ('bim', lambda b: b.replace(b'1\t1\t0\t1', b'13\t1\t0\t1'), 'chromosome'),
    ('bim', lambda b: b.replace(b'G\tA', b'N\tA'), 'allele')])
def test_invalid_plink_inputs(tmp_path, ext, mutate, match):
    import shutil
    for suffix in ['bed', 'bim', 'fam']:
        shutil.copy('tests/fixtures/tiny.' + suffix, tmp_path / ('tiny.' + suffix))
    p = tmp_path / ('tiny.' + ext)
    p.write_bytes(mutate(p.read_bytes()))
    with pytest.raises(ValueError, match=match):
        validate(tmp_path / 'tiny')


def test_missing_quality_fail_policy(tmp_path):
    r = run('tests/fixtures/tiny.vcf.gz', 'tests/fixtures/reference.fa', tmp_path,
            Policy(sample_call_rate=.4, missing_quality='fail'))
    assert r['quality_counts']['failed'] == 2
    assert r['quality_counts']['not_assessed'] == 0


def test_phased_original_call_preserved(tmp_path):
    from pathlib import Path
    import pysam
    p = tmp_path / 'phased.vcf'
    p.write_text(Path('tests/fixtures/tiny.vcf').read_text().replace('0/1:10:30', '0|1:10:30'))
    run(p, 'tests/fixtures/reference.fa', tmp_path / 'out', Policy(sample_call_rate=.4))
    with pysam.VariantFile(str(tmp_path / 'out/masked.vcf.gz')) as f:
        first = next(f)
        assert first.samples['S1']['OGT'] == '0|1'
