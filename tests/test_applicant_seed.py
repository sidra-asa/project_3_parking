"""Quick regression tests for applicants-only campus users (no database needed)."""
from collections import Counter
import random

from demo_data_generator import (
    _keep_only_applicants, _make_users, _make_vehicles,
    build_demo_data, summarize_dataset,
)


def test_owner_only_population():
    rng = random.Random(20261103)
    candidates = _make_users(rng)
    vehicles = _make_vehicles(rng, candidates)
    applicants = _keep_only_applicants(candidates, vehicles)
    ids = {u['id'] for u in applicants}
    assert len(candidates) == 13000
    assert len(vehicles) == 6641
    assert len(applicants) == 4834
    assert ids == {v['user_ref'] for v in vehicles}
    assert ids == set(range(1, len(applicants) + 1))
    assignments = Counter(v['user_ref'] for v in vehicles)
    assert max(assignments.values()) <= 3
    assert any(n > 1 for n in assignments.values())


def test_dataset_has_no_unaffiliated_campus_users():
    rows = build_demo_data(count=1000)
    owner_refs = {v['user_ref'] for v in rows['vehicle']}
    assert owner_refs == {u['id'] for u in rows['campus_user']}
    assert len(rows['parking_record']) == 1000
    assert any(r['permit_ref'] is None for r in rows['parking_record'])
