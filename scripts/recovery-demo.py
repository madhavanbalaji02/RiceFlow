"""Exercise controller finalization, cache reuse, and biological-policy invalidation."""
import argparse
import csv
import json
import re
import subprocess
import uuid
from pathlib import Path

import yaml

parser = argparse.ArgumentParser()
parser.add_argument('--root', default='reports')
parser.add_argument('--config', default='config/demo.yaml')
parser.add_argument('--profile', default='native')
parser.add_argument('--image')
parser.add_argument('--probe-code', action='store_true', help='Native-only temporary source-comment invalidation probe')
args = parser.parse_args()
base = Path(args.root) / ('recovery-' + uuid.uuid4().hex[:8])
base.mkdir(parents=True)

def launch(label, extra, expected):
    out = base / label
    p = subprocess.run(['riceflow', 'run', '--out', str(out), '--config', args.config,
                        '--profile', args.profile, *(['--image', args.image] if args.image else []), *extra])
    assert p.returncode == expected, (out / 'launcher.log').read_text()
    return out

failed = launch('failed', ['--inject-failure'], 1)
assert not (failed / 'SUCCESS.json').exists()
assert (failed / 'failure-manifest.json').exists()
name = re.search(r'Session UUID: ([0-9a-f-]+)', (failed / 'nextflow.log').read_text())[1]
resumed = launch('resumed', ['--resume', name], 0)
rows = list(csv.DictReader((resumed / 'trace.tsv').open(), delimiter='\t'))
assert sum(r['status'] == 'CACHED' for r in rows) == 2, rows
cfg = yaml.safe_load(Path(args.config).read_text())
cfg['policy']['min_dp'] = 6
changed_cfg = base / 'changed.yaml'
changed_cfg.write_text(yaml.safe_dump(cfg))
changed = launch('changed', ['--config', str(changed_cfg), '--resume', name], 0)
rows2 = list(csv.DictReader((changed / 'trace.tsv').open(), delimiter='\t'))
assert all(r['status'] != 'CACHED' for r in rows2), rows2
# Conservative cache key includes full policy: cohort reruns even for VCF-only DP change.
a = json.loads((resumed / 'run-manifest.json').read_text())
assert a['fingerprint'] == json.loads((failed / 'run-manifest.json').read_text())['fingerprint']
b = json.loads((changed / 'run-manifest.json').read_text())
assert a['fingerprint'] != b['fingerprint']
code_probe = None
if args.probe_code:
    if args.profile != 'native':
        raise ValueError('The source-change probe requires native execution')
    source = Path(__file__).resolve().parents[1] / 'src/riceflow/cohort.py'
    original = source.read_bytes()
    probe = b'# RiceFlow temporary native code-cache invalidation probe.\n' + original
    (base / 'code-probe-source.py').write_bytes(probe)
    try:
        source.write_bytes(probe)
        code_changed = launch('code-changed', ['--resume', name], 0)
        trace = list(csv.DictReader((code_changed / 'trace.tsv').open(), delimiter='\t'))
        assert all(r['status'] != 'CACHED' for r in trace), trace
        c = json.loads((code_changed / 'run-manifest.json').read_text())
        assert c['fingerprint'] != a['fingerprint']
        assert c['config']['policy'] == a['config']['policy']
        from compare_biology import compare
        semantics = compare(resumed, code_changed)
        assert semantics['equivalent'], semantics
        code_probe = dict(run=str(code_changed), cached_tasks=0, policy_unchanged=True,
                          biological_outputs_equivalent=True)
    finally:
        if source.read_bytes() != probe:
            raise RuntimeError('Source changed concurrently; retaining new content instead of overwriting it')
        source.write_bytes(original)
(base / 'evidence.json').write_text(json.dumps(dict(failed=str(failed), resumed=str(resumed),
    changed=str(changed), cached_tasks=2, policy_change_cached_tasks=0, code_probe=code_probe), indent=2) + '\n')
print(base)
