#!/usr/bin/env python3
"""Prepared, unexecuted AWS controller. Dedicated queue and explicit authorization required."""
import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

ACTIVE = ['SUBMITTED', 'PENDING', 'RUNNABLE', 'STARTING', 'RUNNING']

def aws(*args):
    p = subprocess.run(['aws', '--region', 'us-east-1', *args, '--output', 'json'],
                       capture_output=True, text=True, timeout=45, check=True)
    return json.loads(p.stdout) if p.stdout.strip() else {}


def jobs(queue):
    found = []
    for status in ACTIVE:
        # AWS CLI auto-pagination remains enabled.
        found.extend(aws('batch', 'list-jobs', '--job-queue', queue, '--job-status', status)['jobSummaryList'])
    return found


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--authorization', required=True, help='User-reviewed per-run cost authorization JSON')
    p.add_argument('--deadline', type=int, default=1800, help='Includes queue wait')
    p.add_argument('command', nargs=argparse.REMAINDER)
    a = p.parse_args()
    from riceflow.cloud import authorize
    authorize(a.authorization)
    os.environ['RICEFLOW_CLOUD_AUTHORIZATION'] = str(Path(a.authorization).resolve())
    queue, bucket = os.environ['RICEFLOW_QUEUE'], os.environ['RICEFLOW_S3']
    if '@sha256:' not in os.environ['RICEFLOW_IMAGE']:
        raise SystemExit('Cloud requires immutable ECR RepoDigest')
    if jobs(queue):
        raise SystemExit('Dedicated queue is not empty; no concurrent cloud runs permitted')
    if not a.command or a.command[0] != 'riceflow':
        raise SystemExit('Provide a reviewed riceflow run --profile aws command')
    child = subprocess.Popen(a.command, start_new_session=True)
    try:
        code = child.wait(timeout=min(a.deadline, 3600))
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        code = 124
    finally:
        remaining = jobs(queue)
        for j in remaining:
            aws('batch', 'terminate-job', '--job-id', j['jobId'], '--reason', 'RiceFlow controller finalization')
        end = time.monotonic() + 180
        while jobs(queue) and time.monotonic() < end:
            time.sleep(10)
        backups = [(['aws', 's3', 'sync', 'reports', bucket + '/results'], 180),
                   (['aws', 's3', 'sync', '.nextflow', bucket + '/controller-backups/.nextflow'], 90)]
        backup_errors = []
        for cmd, timeout in backups:
            try:
                subprocess.run(cmd, check=True, timeout=timeout)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                backup_errors.append(str(e))
        # A stopped controller retains its encrypted EBS even when off-instance backup fails.
        Path('cloud-controller-status.json').write_text(json.dumps(dict(returncode=code,
            active_jobs=jobs(queue), backup_errors=backup_errors,
            worker_idle_verification='REQUIRED externally after managed scale-down')))
        if jobs(queue):
            raise SystemExit('Jobs not terminal. Escalate immediately; controller retained for recovery.')
        # Deliberate cloud-only action: never run this script for local development.
        subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
