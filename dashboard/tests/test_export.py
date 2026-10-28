"""Checks for evidence certification in the read-only dashboard export."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('dashboard_export', ROOT / 'scripts/export_dashboard.py')
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


class DashboardExportTests(unittest.TestCase):
    def test_existing_snapshot_checks_recorded_markers_and_failures(self):
        bundle = EXPORT.build(ROOT)
        latest = bundle['runs'][0]
        self.assertEqual(latest['status'], 'SUCCESS')
        self.assertEqual(latest['certification']['state'], 'verified')
        self.assertEqual(len(latest['tracks']['cohort']['final_sites']), 824)
        historical = next(r for r in bundle['runs'] if r['name'] == 'Historical · incomplete')
        self.assertEqual(historical['status'], 'INCOMPLETE')
        self.assertEqual(historical['certification']['state'], 'absent')

    def test_recorded_variant_quality_is_taken_from_the_audit_ledger(self):
        run = EXPORT.build(ROOT)['runs'][1]
        variant = next(v for v in run['variants'] if v['position'] == 1001391)
        self.assertEqual(run['environment'], 'Native')
        self.assertEqual(variant['gq'], 34)
        self.assertFalse(variant['retained'])
        self.assertEqual(variant['source_filter'], 'LowQual')

    def test_a_tampered_artifact_cannot_be_export_certified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {'run_id': 'fixture', 'status': 'SUCCESS'}
            (root / 'run-manifest.json').write_text(json.dumps(manifest))
            (root / 'artifact.txt').write_text('original')
            (root / 'output-checksums.json').write_text(json.dumps({'artifact.txt': EXPORT.sha(root / 'artifact.txt')}))
            (root / 'SUCCESS.json').write_text(json.dumps({'run_id': 'fixture', 'manifest_sha256': EXPORT.sha(root / 'run-manifest.json'), 'checksums_sha256': EXPORT.sha(root / 'output-checksums.json')}))
            self.assertEqual(EXPORT.certification(root, manifest)['state'], 'verified')
            (root / 'artifact.txt').write_text('changed')
            self.assertEqual(EXPORT.certification(root, manifest)['state'], 'mismatch')

    def test_export_omits_private_local_paths_and_account_configuration(self):
        encoded = json.dumps(EXPORT.build(ROOT))
        self.assertNotIn('/Users/', encoded)
        self.assertNotIn('recipient_verified_against_user_input', encoded)
        self.assertNotIn('nextflow_command', encoded)


if __name__ == '__main__':
    unittest.main()
