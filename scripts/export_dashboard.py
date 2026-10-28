#!/usr/bin/env python3
"""Export recorded RiceFlow artifacts for the read-only, dependency-free dashboard."""
import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_RUNS = [
    ('audit-20261027/linux-publication-follow-up/publication-real', 'Real data · Docker', 'Latest source validation'),
    ('audit-20261027/verified-gq40', 'Real data · GQ40', 'Genotype quality policy'),
    ('audit-20261027/verified-real', 'Real data · baseline', 'Initial verified two-track run'),
    ('deliverable-synthetic', 'Synthetic fixtures', 'Hand-calculated correctness fixtures'),
    ('deliverable-real-cohort', 'Historical · incomplete', 'Archived reference-access blocker'),
    ('audit-20261027/recovery-479558bf/failed', 'Recovery · injected failure', 'Controlled failure before resume'),
    ('audit-20261027/recovery-479558bf/resumed', 'Recovery · resumed', 'Completed tasks reused'),
]


def read(path, fallback=None):
    return json.loads(path.read_text()) if path.is_file() else fallback


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def certification(path, manifest):
    marker = read(path / 'SUCCESS.json', {})
    checks = path / 'output-checksums.json'
    if not marker:
        return {'state': 'absent', 'description': 'No success marker in the recorded run.'}
    valid = (marker.get('run_id') == manifest.get('run_id')
             and marker.get('manifest_sha256') == sha(path / 'run-manifest.json')
             and checks.is_file() and marker.get('checksums_sha256') == sha(checks))
    artifacts = read(checks, {})
    failures = []
    if valid:
        for relative, digest in artifacts.items():
            candidate = path / relative
            if not candidate.resolve().is_relative_to(path.resolve()) or not candidate.is_file() or sha(candidate) != digest:
                failures.append(relative)
        valid = not failures
    return {'state': 'verified' if valid else 'mismatch', 'artifact_count': len(artifacts),
            'description': 'Recorded marker, manifests, and listed artifact hashes checked during export.' if valid
            else 'Success marker or recorded artifact hashes do not match; inspect source evidence.',
            'failed_artifacts': failures}


def export_run(path, name, subtitle, repo):
    manifest = read(path / 'run-manifest.json')
    if not manifest:
        return None
    cert = certification(path, manifest)
    declared = manifest.get('status', 'UNKNOWN')
    status = declared
    if declared == 'SUCCESS' and cert['state'] != 'verified':
        status = 'UNVERIFIED'
    tracks = {name: read(path / name / 'summary.json', {'status': 'UNAVAILABLE'}) for name in ('cohort', 'vcf')}
    files = []
    for filename in ['report.html', 'run-manifest.json', 'SUCCESS.json', 'output-checksums.json', 'trace.tsv', 'policy.json']:
        if (path / filename).is_file():
            relative = (path / filename).relative_to(repo).as_posix()
            files.append({'name': filename, 'url': 'https://github.com/madhavanbalaji02/RiceFlow/blob/' + repo_commit(repo) + '/' + relative,
                          'sha256': sha(path / filename), 'bytes': (path / filename).stat().st_size})
    variants = []
    # The audit ledger preserves original calls and per-record qualities without requiring raw inputs.
    source = path / 'vcf' / 'audit.tsv'
    if source.is_file():
        for row in csv.DictReader(source.read_text().splitlines(), delimiter='\t'):
            if row.get('kind') != 'snp':
                continue
            fields = row['locus'].split(':')
            variants.append({'locus': row['locus'], 'position': int(fields[1]), 'ref': fields[2], 'alt': fields[3],
                             'source_filter': row.get('source_filter'), 'genotype': row.get('original_gt'),
                             'quality_status': row.get('quality_status'), 'reasons': row.get('reasons'),
                             'retained': row.get('retained') == 'True',
                             'dp': int(row['dp']) if row.get('dp') else None,
                             'gq': int(row['gq']) if row.get('gq') else None})
    # Tools and source hashes are useful; local absolute paths and command-line arguments are omitted.
    config = manifest.get('config', {})
    return {'id': manifest.get('run_id', path.name), 'name': name, 'subtitle': subtitle,
            'status': status, 'declared_status': declared, 'certification': cert,
            'kind': 'synthetic' if manifest.get('label') == 'SYNTHETIC' else 'real',
            'started': manifest.get('started'), 'ended': manifest.get('ended'),
            'workflow_seconds': manifest.get('elapsed_seconds'),
            'environment': 'Native' if manifest.get('image') in (None, 'NATIVE_NO_IMAGE') else 'Docker',
            'policy': config.get('policy', read(path / 'policy.json', {})), 'tracks': tracks,
            'tasks': manifest.get('tasks', []), 'inputs': manifest.get('inputs', {}),
            'fingerprint': manifest.get('fingerprint'), 'image': manifest.get('image'),
            'git': manifest.get('git', {}), 'tools': {k: str(v).split('\n')[0] for k, v in manifest.get('tools', {}).items()},
            'error': manifest.get('error'), 'files': files, 'variants': variants,
            'source_path': path.relative_to(repo).as_posix()}


def repo_commit(repo):
    return subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()


def build(repo):
    runs = [export_run(repo / 'reports' / rel, name, subtitle, repo) for rel, name, subtitle in DEFAULT_RUNS]
    index = read(repo / 'reports' / 'validation-summary.json', {})
    cloud = read(repo / 'reports' / 'aws-demo-20261027-summary.json', {})
    # Only public scientific/operational fields are exposed. No account IDs, credentials, or email addresses.
    cloud_view = {key: cloud.get(key) for key in ('status', 'checked_utc', 'region', 'science', 'estimate', 'remaining_cloud_gates')}
    cloud_view['shutdown'] = {key: cloud.get('shutdown', {}).get(key) for key in ('status', 'controller', 'workers', 'batch_desired_vcpus', 'independent_observation_utc')}
    cloud_view['budget'] = {'target_usd': cloud.get('project_monthly_target_usd'), 'thresholds_usd': cloud.get('budget', {}).get('thresholds_usd')}
    return {'schema_version': 1, 'exported_at': datetime.now(timezone.utc).isoformat(),
            'repository': 'https://github.com/madhavanbalaji02/RiceFlow', 'source_commit': repo_commit(repo),
            'data_note': 'Recorded artifact snapshot, not live pipeline or AWS monitoring. This dashboard does not launch jobs.',
            'runs': [r for r in runs if r], 'validation': {'tests': index.get('tests'), 'reproducibility': index.get('reproducibility'),
            'recovery': {'cached_tasks': index.get('recovery', {}).get('cached_tasks')},
            'source_samples': index.get('cohort', {}).get('source_samples'), 'source_loci': index.get('cohort', {}).get('source_loci')},
            'cloud': cloud_view}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    destination = args.output or args.repo / 'dashboard' / 'data.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = build(args.repo.resolve())
    destination.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False))
    print(f'Exported {len(data["runs"])} recorded runs to {destination}')


if __name__ == '__main__':
    main()
