import json
from datetime import datetime, timezone

import pytest

from riceflow.cloud import authorize


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
