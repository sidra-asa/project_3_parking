"""Offline integrity verification for fictional demo data, no database needed."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
import heapq
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from demo_data_generator import build_demo_data, TAIPEI  # noqa: E402
from campus_parking_areas import (  # noqa: E402
    CAR_AREAS, MOTORCYCLE_AREAS, CAR_VISITOR_NUMBERS,
    MOTORCYCLE_VISITOR_NUMBERS, CAR_STUDENT_PERMIT_NUMBERS,
)


def validate(rows):
    users = {u['id']: u for u in rows['campus_user']}
    vehicles = {v['id']: v for v in rows['vehicle']}
    vehicles_by_plate = {v['plate_no']: v for v in vehicles.values()}
    areas = {a['id']: a for a in rows['parking_area']}
    permits = {p['id']: p for p in rows['parking_permit']}
    expected = {(typ, no): (name, cap) for typ, table in
                (('CAR', CAR_AREAS), ('MOTORCYCLE', MOTORCYCLE_AREAS))
                for no, name, cap in table}
    assert len(users) == 1500
    assert len(vehicles) == 900
    assert len(areas) == 49
    assert len(permits) == 1200
    assert len(rows['parking_record']) == 30000
    assert len({v['plate_no'] for v in vehicles.values()}) == 900
    assert all(v['user_ref'] in users for v in vehicles.values())
    assert {v['id'] for v in vehicles.values()} == {p['vehicle_ref'] for p in permits.values()}
    assert len({(p['vehicle_ref'], p['academic_year']) for p in permits.values()}) == 1200
    assert sum(a['capacity'] for a in areas.values() if a['vehicle_type'] == 'CAR') == 870
    assert sum(a['capacity'] for a in areas.values() if a['vehicle_type'] == 'MOTORCYCLE') == 6306
    assert all((a['area_name'], a['capacity']) ==
               expected[(a['vehicle_type'], a['map_no'])] for a in areas.values())

    events = sorted(rows['parking_record'], key=lambda r: r['entry_time'])
    last_exit = {}
    occupancy = defaultdict(list)
    active_set = set()
    for rec in events:
        plate = rec['plate_no']
        v = vehicles_by_plate.get(plate)
        a = areas[rec['area_ref']]
        if v is not None:
            assert a['vehicle_type'] == v['vehicle_type'], rec['id']
        else:
            assert plate.startswith('DEMO-GC-') if a['vehicle_type'] == 'CAR' else plate.startswith('DEMO-GM-')
        if rec['permit_ref'] is None:
            assert v is None, ('guest must not have a Vehicle row', rec['id'])
            assert a['map_no'] in (CAR_VISITOR_NUMBERS if a['vehicle_type'] == 'CAR'
                                   else MOTORCYCLE_VISITOR_NUMBERS), rec['id']
        elif a['vehicle_type'] == 'CAR':
            owner_type = users[v['user_ref']]['identity_type']
            if owner_type == 'STUDENT':
                assert a['map_no'] in CAR_STUDENT_PERMIT_NUMBERS, rec['id']
            else:
                assert not a['visitor'], rec['id']
        else:
            assert not a['visitor'], rec['id']
        assert rec['entry_time'].tzinfo is not None
        assert rec['id'] > 0
        last = last_exit.get(plate)
        assert last is None or last <= rec['entry_time'], (plate, rec['id'], 'vehicle overlap')
        h = occupancy[a['id']]
        while h and h[0] <= rec['entry_time']:
            heapq.heappop(h)
        assert len(h) < a['capacity'], (a['id'], rec['id'], 'area full')
        if rec['exit_time'] is not None:
            assert rec['exit_time'] > rec['entry_time']
            assert rec['parking_fee'] is not None
            assert rec['parking_fee'] >= 0
            until = rec['exit_time']
            if rec['permit_ref']:
                permit = permits[rec['permit_ref']]
                assert permit['vehicle_ref'] == v['id']
                assert permit['paid_at'] is not None
                assert permit['paid_at'] <= rec['entry_time']
                assert permit['valid_from'] <= rec['entry_time'].astimezone(TAIPEI).date()
                assert rec['exit_time'].astimezone(TAIPEI).date() <= permit['valid_to']
                assert rec['parking_fee'] == 0
            else:
                assert rec['parking_fee'] > 0 or (a['vehicle_type'] == 'MOTORCYCLE'
                                                        and a['visitor'])
            if rec['paid_at'] is None:
                assert rec['payment_method'] is None
            else:
                assert rec['parking_fee'] > 0 or (a['vehicle_type'] == 'MOTORCYCLE'
                                                        and a['visitor'])
                assert rec['payment_method'] is not None
                assert rec['paid_at'] >= rec['exit_time']
        else:
            assert rec['parking_fee'] is None
            assert rec['payment_method'] is None and rec['paid_at'] is None
            assert plate not in active_set
            active_set.add(plate)
            until = datetime.max.replace(tzinfo=rec['entry_time'].tzinfo)
        heapq.heappush(h, until)
        last_exit[plate] = until
    assert len(active_set) == 450
    return True


if __name__ == '__main__':
    data = build_demo_data(as_of=datetime.fromisoformat('2026-11-03T18:00:00+08:00'))
    validate(data)
    print('PASS: 30,000 rows, time non-overlap, area capacity, permits and payments')
