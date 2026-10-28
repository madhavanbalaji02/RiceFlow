import json
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from riceflow.cloud import authorize


def test_controller_uses_reviewed_region(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        'cloud_controller', Path(__file__).parents[1] / 'scripts/cloud-controller.py')
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout='{}')

    monkeypatch.setattr(controller.subprocess, 'run', run)
    monkeypatch.delenv('AWS_REGION', raising=False)
    monkeypatch.delenv('AWS_DEFAULT_REGION', raising=False)
    with pytest.raises(ValueError, match='reviewed deployment region'):
        controller.aws('batch', 'list-jobs')
    assert not calls
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-2')
    controller.aws('batch', 'list-jobs')
    assert calls[-1][2] == 'us-east-2'
    monkeypatch.setenv('AWS_REGION', 'us-west-2')
    controller.aws('batch', 'list-jobs')
    assert calls[-1][2] == 'us-west-2'


def test_cloud_cost_gate(tmp_path):
    p = tmp_path / 'approval.json'
    record = dict(approved_by_user=True, conservative_run_usd=2, observed_month_usd=1,
                  retained_month_usd=1, worker_hours_used=0, controller_hours_used=0,
                  planned_worker_hours=1, planned_controller_hours=1,
                  estimate_verified_utc=datetime.now(timezone.utc).isoformat())
    p.write_text(json.dumps(record))
    assert authorize(p)['conservative_run_usd'] == 2
    record['observed_month_usd'] = 14
    p.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='15'):
        authorize(p)
    record['observed_month_usd'] = None
    p.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='nonnegative'):
        authorize(p)
    record['observed_month_usd'] = 0
    record['worker_hours_used'] = 20
    p.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='hour'):
        authorize(p)


def test_worker_verification_excludes_only_controller(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        'cloud_controller_workers', Path(__file__).parents[1] / 'scripts/cloud-controller.py')
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    monkeypatch.setenv('RICEFLOW_CONTROLLER_ID', 'i-controller')
    calls = []

    def aws(*args):
        calls.append(args)
        return {'Reservations': [{'Instances': [{'InstanceId': 'i-controller'},
                                                {'InstanceId': 'i-worker'}]}]}

    monkeypatch.setattr(controller, 'aws', aws)
    assert controller.workers() == ['i-worker']
    assert 'Name=instance-state-name,Values=pending,running,stopping' in calls[0]
