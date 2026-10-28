"""Public asset allowlist, privacy gate and Free-plan deployment invariants."""
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
hosting = importlib.import_module('dashboard_aws')
publisher = importlib.import_module('publish_dashboard')


class PublishingTests(unittest.TestCase):
    def test_only_required_static_assets_are_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'site'
            result = publisher.publish(ROOT, output)
            self.assertEqual(len(result['assets']), 6)
            self.assertEqual({p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}, set(result['assets']))
            data_file = next(p for p in output.rglob('data.*.json'))
            snapshot = json.loads(data_file.read_text())
            self.assertEqual(len(snapshot['runs'][0]['tracks']['cohort']['final_sites']), 824)
            self.assertIn('FAILED', result['run_statuses'])
            self.assertIn('INCOMPLETE', result['run_statuses'])
            app = next(output.rglob('app.*.js')).read_text()
            self.assertIn('import.meta.url', app)
            self.assertEqual(hosting.load_assets(output)['total_bytes'], result['total_bytes'])
            (output / 'private.log').write_text('not a public asset')
            with self.assertRaises(ValueError):
                hosting.load_assets(output)
            with self.assertRaises(ValueError):
                publisher.publish(ROOT, output)
            self.assertTrue((output / 'private.log').exists())

    def test_public_metadata_gate_rejects_private_fields_and_paths(self):
        for value in [{'AWS_SECRET_ACCESS_KEY': 'example'}, '/Users/example/private',
                      'arn:aws:iam::123456789012:role/private', '123456789012']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                publisher.check_snapshot(value)
        publisher.check_snapshot({'job': '73c7e0ab-9795-4c9e-9997-390944432368'})

    def test_existing_unowned_directory_is_never_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'existing'
            path.mkdir()
            (path / 'unrelated.txt').write_text('keep')
            with self.assertRaises(ValueError):
                publisher.publish(ROOT, path)
            self.assertEqual((path / 'unrelated.txt').read_text(), 'keep')

    def test_only_active_matching_free_subscription_is_accepted(self):
        output = {'DistributionArn': 'distribution', 'WebACLArn': 'acl'}
        good = {'subscription': {'planFamily': 'CloudFront', 'planTier': 'FREE',
                                'status': 'ACTIVE', 'resourceArns': ['distribution', 'acl']}}
        hosting.verify_free(good, output)
        for field, value in [('planTier', 'PRO'), ('status', 'PENDING_APPROVAL'),
                             ('resourceArns', ['unrelated', 'acl']), ('scheduledChange', {'planTier': 'PRO'})]:
            changed = json.loads(json.dumps(good))
            changed['subscription'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                hosting.verify_free(changed, output)

    def test_template_has_no_backend_or_paid_plan_and_keeps_s3_private(self):
        template = json.loads(hosting.TEMPLATE.read_text())
        hosting.check_template(template)
        self.assertEqual(template['Parameters']['SiteEnabled']['Default'], 'false')
        self.assertEqual(template['Resources']['DashboardFreeSubscription']['Properties']['PlanTier'], 'FREE')
        template['Resources']['DashboardFreeSubscription']['Properties']['PlanTier'] = 'PRO'
        with self.assertRaises(ValueError):
            hosting.check_template(template)

    def test_unrelated_stack_is_never_adopted(self):
        with self.assertRaises(ValueError):
            hosting.owned({'Tags': [{'Key': 'Project', 'Value': 'DifferentProject'}]})


if __name__ == '__main__':
    unittest.main()
