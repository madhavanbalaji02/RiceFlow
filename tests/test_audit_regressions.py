import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from riceflow.cli import finalize
from riceflow.common import Policy, dump, sha
from riceflow.validation import validate_track, verify_real_inputs
from riceflow.vcf import assess_quality, run


def test_git_metadata_optional_for_source_archives(tmp_path, monkeypatch):
    from riceflow import cli
    assert cli.git_state(tmp_path)['commit'] is None

    def missing_git(*args):
        raise FileNotFoundError('git')

    monkeypatch.setattr(cli, 'command', missing_git)
    assert cli.git_state(tmp_path) == dict(commit=None, dirty=None, status='Git metadata unavailable')


def test_failed_refinalization_revokes_old_success(tmp_path):
    (tmp_path / 'SUCCESS.json').write_text('{"status":"old success"}')
    assert finalize(tmp_path, dict(run_id='failed', label='SYNTHETIC'), 42) == 1
    assert not (tmp_path / 'SUCCESS.json').exists()
    manifest = json.loads((tmp_path / 'failure-manifest.json').read_text())
    assert manifest['track_statuses'] == {'cohort': 'BLOCKED', 'vcf': 'BLOCKED'}


def real_attestation(tmp_path):
    cfg = dict(cohort='tests/fixtures/tiny', vcf='tests/fixtures/tiny.vcf.gz',
               reference='tests/fixtures/reference.fa', expected_sample='S1', vcf_region='chr01:1-9',
               source_manifest=str(tmp_path / 'source.json'))
    source = dict(sources=[dict(url=f'https://example.test/core.{ext}.gz',
                              decompressed_sha256=sha(cfg['cohort'] + '.' + ext))
                           for ext in ['bed', 'bim', 'fam']],
                  tracks=dict(cohort=dict(status='VERIFIED'),
                              vcf=dict(status='VERIFIED', sha256=sha(cfg['vcf']), samples=['S1'],
                                       region=cfg['vcf_region'], index_sha256=sha(cfg['vcf'] + '.tbi'))),
                  reference=dict(status='VERIFIED_REGIONAL_BASES', sha256=sha(cfg['reference'])))
    dump(cfg['source_manifest'], source)
    return cfg, source


@pytest.mark.parametrize('field,value', [('sha256', 'bad'), ('status', 'BLOCKED'), ('samples', ['other']),
                                        ('index_sha256', None), ('region', 'chr01:20-30')])
def test_real_vcf_identity_is_mandatory(tmp_path, field, value):
    cfg, source = real_attestation(tmp_path)
    assert verify_real_inputs(cfg)['tracks']['vcf']['status'] == 'VERIFIED'
    source['tracks']['vcf'][field] = value
    dump(cfg['source_manifest'], source)
    with pytest.raises(ValueError, match='identity|selection'):
        verify_real_inputs(cfg)


def test_reference_records_and_source_filters_preserved(tmp_path):
    import pysam
    result = run('tests/fixtures/tiny.vcf.gz', 'tests/fixtures/reference.fa', tmp_path,
                 Policy(sample_call_rate=.4), 'S1', 'chr01:1-9')
    assert result['scope_counts'] == dict(reference=1, unsupported=1, snp=7)
    with pysam.VariantFile(str(tmp_path / 'reference-records.vcf.gz')) as f:
        records = list(f.fetch())
        assert records[0].samples['S1']['GT'] == (0, 0)
        assert records[0].pos == 1
    assert validate_track(tmp_path, 'vcf')['status'] == 'PASS'
    pq.write_table(pa.table({'fake': [1]}), tmp_path / 'final_sites.parquet')
    with pytest.raises(ValueError, match='Parquet'):
        validate_track(tmp_path, 'vcf')


def test_quality_missing_reason_not_duplicated():
    status, reason = assess_quality(dict(locus='x', dp=None, gq=5),
                                    Policy(min_gq=20, missing_quality='fail'))
    assert status == 'failed'
    assert reason.split(';').count('missing_dp') == 1


def test_vcf_interval_must_match_actual_records(tmp_path):
    with pytest.raises(ValueError, match='outside configured interval'):
        run('tests/fixtures/tiny.vcf.gz', 'tests/fixtures/reference.fa', tmp_path,
            Policy(), 'S1', 'chr01:2-8')


def test_sensitivity_uses_baseline_missing_field_policy(tmp_path):
    p = Policy(sample_call_rate=.4, min_dp=None, min_gq=None)
    result = run('tests/fixtures/tiny.vcf.gz', 'tests/fixtures/reference.fa', tmp_path, p)
    baseline = result['sensitivity'][0]
    assert baseline['min_dp'] is None
    assert baseline['retained_sites'] == len(result['final_sites'])
    assert all(x['min_gq'] is None and x['sample_call_rate'] == .4 for x in result['sensitivity'])


def test_identical_ref_alt_is_not_a_snp(tmp_path):
    p = tmp_path / 'identical.vcf'
    p.write_text(Path('tests/fixtures/tiny.vcf').read_text().replace('chr01\t2\t.\tA\tG', 'chr01\t2\t.\tA\tA'))
    result = run(p, 'tests/fixtures/reference.fa', tmp_path / 'out', Policy(sample_call_rate=0))
    assert result['scope_counts']['unsupported'] == 2


def test_nonfinite_quality_cannot_pass():
    with pytest.raises(ValueError, match='Invalid dp'):
        assess_quality(dict(locus='x', dp=float('nan'), gq=None), Policy())


def test_invalid_completed_track_cannot_certify(tmp_path):
    (tmp_path / 'cohort').mkdir()
    dump(tmp_path / 'cohort/summary.json', dict(status='PASS'))
    assert finalize(tmp_path, dict(run_id='bad', label='SYNTHETIC'), 0) == 1
    m = json.loads((tmp_path / 'failure-manifest.json').read_text())
    assert m['track_statuses']['cohort'] == 'FAILED_VALIDATION'
    assert m['status'] == 'FAILED'
    assert not (tmp_path / 'SUCCESS.json').exists()


def test_corrupt_trace_cannot_certify(tmp_path):
    (tmp_path / 'trace.tsv').write_text('unrelated\nvalue\n')
    assert finalize(tmp_path, dict(run_id='bad-trace', label='SYNTHETIC'), 0) == 1
    m = json.loads((tmp_path / 'failure-manifest.json').read_text())
    assert 'Trace lacks' in m['error']
    assert not (tmp_path / 'SUCCESS.json').exists()


def test_tsv_value_corruption_is_rejected(tmp_path):
    run('tests/fixtures/tiny.vcf.gz', 'tests/fixtures/reference.fa', tmp_path, Policy(sample_call_rate=.4))
    p = tmp_path / 'final_samples.tsv'
    p.write_text(p.read_text().replace('S1', 'different_sample'))
    with pytest.raises(ValueError, match='TSV values'):
        validate_track(tmp_path, 'vcf')


def test_empty_table_schema_is_verified(tmp_path):
    run('tests/fixtures/tiny.vcf.gz', 'tests/fixtures/reference.fa', tmp_path, Policy(sample_call_rate=.4))
    pq.write_table(pa.table({'wrong_empty_column': pa.array([], pa.string())}), tmp_path / 'excluded_samples.parquet')
    with pytest.raises(ValueError, match='empty Parquet schema'):
        validate_track(tmp_path, 'vcf')
