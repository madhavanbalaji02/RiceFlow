"""Exercise controller finalization, cache reuse, and biological-policy invalidation."""
import csv
import json
import re
import subprocess
import uuid
from pathlib import Path

import yaml

base = Path('reports') / ('recovery-' + uuid.uuid4().hex[:8])
base.mkdir(parents=True)

def launch(label, extra, expected):
    out = base / label
    p = subprocess.run(['riceflow', 'run', '--out', str(out), *extra])
    assert p.returncode == expected, (out / 'launcher.log').read_text()
    return out

failed = launch('failed', ['--inject-failure'], 1)
assert not (failed / 'SUCCESS.json').exists()
assert (failed / 'failure-manifest.json').exists()
name = re.search(r'Session UUID: ([0-9a-f-]+)', (failed / 'nextflow.log').read_text())[1]
resumed = launch('resumed', ['--resume', name], 0)
rows = list(csv.DictReader((resumed / 'trace.tsv').open(), delimiter='\t'))
assert sum(r['status'] == 'CACHED' for r in rows) == 2, rows
cfg = yaml.safe_load(Path('config/demo.yaml').read_text())
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
(base / 'evidence.json').write_text(json.dumps(dict(failed=str(failed), resumed=str(resumed),
    changed=str(changed), cached_tasks=2, policy_change_cached_tasks=0), indent=2) + '\n')
print(base)
