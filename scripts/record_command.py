"""Execute an exact command, recording its exit code, log, wall time and OS rusage."""
import argparse
import json
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--ledger', required=True)
p.add_argument('--name', required=True)
p.add_argument('command', nargs=argparse.REMAINDER)
a = p.parse_args()
args = a.command[1:] if a.command and a.command[0] == '--' else a.command
ledger = Path(a.ledger)
ledger.parent.mkdir(parents=True, exist_ok=True)
log = ledger.parent / (a.name + '.log')
if log.exists():
    raise SystemExit('Command logs are immutable; choose a new name')
started = time.monotonic()
record = dict(command=args, cwd=str(Path.cwd()), started_utc=datetime.now(timezone.utc).isoformat(),
              environment=dict(platform=platform.platform(), profile=os.environ.get('RICEFLOW_AUDIT_PROFILE')),
              log=str(log))
with log.open('w') as f:
    child = subprocess.Popen(args, stdout=f, stderr=subprocess.STDOUT)
    _, status, usage = os.wait4(child.pid, 0)
    code = os.waitstatus_to_exitcode(status)
    child.returncode = code
record.update(exit_code=code, elapsed_seconds=time.monotonic() - started,
              ended_utc=datetime.now(timezone.utc).isoformat(),
              max_rss_bytes=usage.ru_maxrss * (1 if platform.system() == 'Darwin' else 1024),
              user_seconds=usage.ru_utime, system_seconds=usage.ru_stime,
              memory_definition='OS wait4 child process-tree high-water RSS; not sum of simultaneous process RSS')
with ledger.open('a') as f:
    f.write(json.dumps(record, sort_keys=True) + '\n')
print(json.dumps(record, sort_keys=True))
raise SystemExit(code if code >= 0 else 1)
