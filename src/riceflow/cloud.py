"""Pure validation only; importing this module never calls AWS."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def authorize(path):
    a = json.loads(Path(path).read_text())
    numeric = ['conservative_run_usd', 'observed_month_usd', 'retained_month_usd',
               'worker_hours_used', 'controller_hours_used', 'planned_worker_hours', 'planned_controller_hours']
    if a.get('approved_by_user') is not True or any(k not in a for k in numeric):
        raise ValueError('Specific user authorization and complete usage/cost evidence required')
    if any(not isinstance(a[k], (int, float)) or isinstance(a[k], bool) or not math.isfinite(a[k]) or a[k] < 0 for k in numeric):
        raise ValueError('Costs/hours must be nonnegative numbers')
    if sum(a[k] for k in numeric[:3]) > 15:
        raise ValueError('Estimated project cost exceeds USD 15; obtain a revised specific approval')
    for kind in ['worker', 'controller']:
        if a[f'{kind}_hours_used'] + a[f'planned_{kind}_hours'] > 20:
            raise ValueError('Aggregate monthly hour ceiling exceeded')
    verified = datetime.fromisoformat(a['estimate_verified_utc'])
    age = (datetime.now(timezone.utc) - verified).total_seconds()
    if age < 0 or age > 86400:
        raise ValueError('Price/usage evidence must be verified within the past 24 hours')
    return a
