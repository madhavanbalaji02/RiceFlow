#!/usr/bin/env python3
"""AWS controller for a dedicated queue and an explicitly authorized, bounded run."""
import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

ACTIVE = ['SUBMITTED', 'PENDING', 'RUNNABLE', 'STARTING', 'RUNNING']

def aws(*args):
    region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
    if not region:
        raise ValueError('Set AWS_REGION or AWS_DEFAULT_REGION to the reviewed deployment region')
    p = subprocess.run(['aws', '--region', region, *args, '--output', 'json'],
                       capture_output=True, text=True, timeout=45, check=True)
    return json.loads(p.stdout) if p.stdout.strip() else {}


def jobs(queue):
    found = []
    for status in ACTIVE:
        # AWS CLI auto-pagination remains enabled.
        found.extend(aws('batch', 'list-jobs', '--job-queue', queue, '--job-status', status)['jobSummaryList'])
    return found


def workers():
    controller = os.environ['RICEFLOW_CONTROLLER_ID']
    reservations = aws('ec2', 'describe-instances', '--filters',
                       'Name=tag:Project,Values=RiceFlow',
                       'Name=instance-state-name,Values=pending,running,stopping')['Reservations']
    return [i['InstanceId'] for r in reservations for i in r['Instances']
            if i['InstanceId'] != controller]


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
    if not os.environ.get('RICEFLOW_CONTROLLER_ID'):
        raise SystemExit('RICEFLOW_CONTROLLER_ID is required to verify worker shutdown')
    if not 1 <= a.deadline <= 1800:
        raise SystemExit('Controller run deadline must be 1–1800 seconds')
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
            operation = 'cancel-job' if j['status'] in ['SUBMITTED', 'PENDING', 'RUNNABLE'] else 'terminate-job'
            aws('batch', operation, '--job-id', j['jobId'], '--reason', 'RiceFlow controller finalization')
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
        if jobs(queue):
            raise SystemExit('Jobs not terminal. Escalate immediately; controller retained for recovery.')
        end = time.monotonic() + 600
        while workers() and time.monotonic() < end:
            time.sleep(20)
        remaining_workers = workers()
        # Retained EBS preserves metadata even when off-instance backup fails.
        status = Path('cloud-controller-status.json')
        status.write_text(json.dumps(dict(returncode=code, active_jobs=[],
            backup_errors=backup_errors, active_workers=remaining_workers,
            worker_idle_verification='PASS' if not remaining_workers else 'FAILED')))
        try:
            subprocess.run(['aws', 's3', 'cp', str(status), bucket + '/results/' + status.name],
                           check=True, timeout=45)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass  # Status remains on the persistent root volume.
        if remaining_workers:
            raise SystemExit('Workers have not reached zero. Controller retained for recovery.')
        # Deliberate cloud-only action: never run this script for local development.
        subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
