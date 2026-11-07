"""Offline integrity and plausibility checks; does not access PostgreSQL."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import heapq
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from demo_data_generator import (  # noqa: E402
    build_demo_data, DEFAULT_AS_OF, END_DATE, HOLIDAYS, PERMIT_COUNTS,
    START_DATE, TAIPEI, USER_COUNTS, _phase,
)
from campus_parking_areas import (  # noqa: E402
    CAR_AREAS, MOTORCYCLE_AREAS, CAR_VISITOR_NUMBERS,
    MOTORCYCLE_VISITOR_NUMBERS, CAR_STUDENT_PERMIT_NUMBERS,
)


def validate(rows, expected_records=30000, as_of=DEFAULT_AS_OF):
    as_of = as_of.astimezone(timezone.utc)
    users = {u['id']: u for u in rows['campus_user']}
    vehicles = {v['id']: v for v in rows['vehicle']}
    vehicles_by_plate = {v['plate_no']: v for v in vehicles.values()}
    areas = {a['id']: a for a in rows['parking_area']}
    permits = {p['id']: p for p in rows['parking_permit']}
    expected_area = {(typ, no): (name, cap) for typ, table in
                     (('CAR', CAR_AREAS), ('MOTORCYCLE', MOTORCYCLE_AREAS))
                     for no, name, cap in table}
    expected_users = sum(USER_COUNTS.values())
    expected_vehicles = sum(PERMIT_COUNTS.values())

    assert len(users) == expected_users
    assert Counter(u['identity_type'] for u in users.values()) == USER_COUNTS
    assert len(vehicles) == expected_vehicles
    assert len({v['plate_no'] for v in vehicles.values()}) == expected_vehicles
    assert sum(v['vehicle_type'] == 'CAR' for v in vehicles.values()) == PERMIT_COUNTS['CAR']
    assert sum(v['vehicle_type'] == 'MOTORCYCLE' for v in vehicles.values()) == PERMIT_COUNTS['MOTORCYCLE']
    assert all(v['user_ref'] in users for v in vehicles.values())
    assert max(Counter(v['user_ref'] for v in vehicles.values()).values()) <= 3
    assert len(permits) == expected_vehicles
    assert all(p['academic_year'] == '114' for p in permits.values())
    assert len({(p['vehicle_ref'], p['academic_year']) for p in permits.values()}) == len(permits)
    assert {p['vehicle_ref'] for p in permits.values()} == set(vehicles)
    assert len(areas) == 49
    assert sum(a['capacity'] for a in areas.values() if a['vehicle_type'] == 'CAR') == 870
    assert sum(a['capacity'] for a in areas.values() if a['vehicle_type'] == 'MOTORCYCLE') == 6306
    assert all((a['area_name'], a['capacity']) == expected_area[(a['vehicle_type'], a['map_no'])]
               for a in areas.values())
    assert len(rows['parking_record']) == expected_records

    records = sorted(rows['parking_record'], key=lambda r: r['entry_time'])
    open_plates = set()
    last_by_plate, last_by_user = {}, {}
    occupancy = defaultdict(list)
    phase_counts = Counter()
    by_date = Counter()
    for r in records:
        plate = r['plate_no']
        vehicle = vehicles_by_plate.get(plate)
        area = areas[r['area_ref']]
        start = r['entry_time']
        assert start.tzinfo is not None and start <= as_of
        local_day = start.astimezone(TAIPEI).date()
        assert START_DATE <= local_day <= END_DATE, (r['id'], local_day)
        assert r['id'] > 0
        assert last_by_plate.get(plate, datetime.min.replace(tzinfo=timezone.utc)) <= start, (
            'overlapping same vehicle', r['id'], plate)
        if vehicle is not None:
            assert area['vehicle_type'] == vehicle['vehicle_type']
            uid = vehicle['user_ref']
            assert last_by_user.get(uid, datetime.min.replace(tzinfo=timezone.utc)) <= start, (
                'user simultaneously driving multiple vehicles', r['id'], uid)
        else:
            assert plate.startswith('DEMO-GC-' if area['vehicle_type'] == 'CAR' else 'DEMO-GM-')

        if r['permit_ref'] is None:
            assert vehicle is None, ('non-guest without permit', r['id'])
            assert area['map_no'] in (CAR_VISITOR_NUMBERS if area['vehicle_type'] == 'CAR'
                                     else MOTORCYCLE_VISITOR_NUMBERS)
        else:
            assert vehicle is not None
            p = permits[r['permit_ref']]
            assert p['vehicle_ref'] == vehicle['id'] and p['paid_at'] is not None
            assert p['paid_at'] <= start
            assert p['valid_from'] <= local_day <= p['valid_to']
            if area['vehicle_type'] == 'CAR':
                if users[vehicle['user_ref']]['identity_type'] == 'STUDENT':
                    assert area['map_no'] in CAR_STUDENT_PERMIT_NUMBERS
                else:
                    assert not area['visitor']
            else:
                assert not area['visitor']

        heap = occupancy[area['id']]
        while heap and heap[0] <= start:
            heapq.heappop(heap)
        assert len(heap) < area['capacity'], ('capacity exceeded', area['id'], r['id'])

        if r['exit_time'] is None:
            assert r['parking_fee'] is None
            assert r['payment_method'] is None and r['paid_at'] is None
            assert plate not in open_plates
            open_plates.add(plate)
            until = datetime.max.replace(tzinfo=timezone.utc)
        else:
            until = r['exit_time']
            assert start < until <= as_of, ('completed record ends after snapshot', r['id'])
            assert r['parking_fee'] is not None and r['parking_fee'] >= 0
            if r['permit_ref'] is not None:
                assert r['parking_fee'] == 0
                assert until.astimezone(TAIPEI).date() <= permits[r['permit_ref']]['valid_to']
                assert r['paid_at'] is None and r['payment_method'] is None
            elif area['vehicle_type'] == 'MOTORCYCLE':
                assert r['parking_fee'] == 0
                assert r['payment_method'] is None and r['paid_at'] is None
            else:
                assert r['parking_fee'] > 0
                assert r['payment_method'] is not None
                assert start <= r['paid_at'] <= until, ('payment after exit', r['id'])
        heapq.heappush(heap, until)
        last_by_plate[plate] = until
        if vehicle is not None:
            last_by_user[vehicle['user_ref']] = until
        phase_counts[_phase(local_day)] += 1
        by_date[local_day] += 1

    assert len(open_plates) > 0, 'snapshot has no parked cars'
    # These relative trends are the intended simulation, not measured counts.
    if expected_records == 30000:
        assert phase_counts == {'classes': 9900, 'exams': 8900,
                                'summer_week_1': 5200, 'summer_week_2': 6000}
        assert by_date[START_DATE] > by_date[START_DATE.replace(day=7)]
        assert by_date[END_DATE.replace(day=19)] < by_date[END_DATE.replace(day=18)]
    return True


def main():
    rows = build_demo_data()
    validate(rows)
    print(f'PASS: {len(rows["campus_user"]):,} users, {len(rows["vehicle"]):,} vehicles, '
          f'{len(rows["parking_permit"]):,} permits, {len(rows["parking_record"]):,} records; '
          f'{sum(r["exit_time"] is None for r in rows["parking_record"]):,} open at snapshot')


if __name__ == '__main__':
    main()
