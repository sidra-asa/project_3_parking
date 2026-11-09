"""Offline 30k-record seed verification; safe without any database connection."""

from demo_data_generator import DEFAULT_AS_OF, build_demo_data, summarize_dataset
from scripts.validate_demo_data import validate


def test_seed_30000_integrity():
    rows = build_demo_data(as_of=DEFAULT_AS_OF)
    assert validate(rows)
    s = summarize_dataset(rows)
    assert s['records'] == 30000
    assert s['campus_users'] == 4834
    assert s['vehicles'] == 6641
    assert s['permits'] == 6641
    assert s['closed_records'] + s['active_records'] == 30000
    assert 0 < s['active_records'] < 1000
    assert s['start_date'] == '2026-06-01'
    assert s['end_date'] == '2026-06-28'
    assert s['by_phase'] == {
        'classes': 9900, 'exams': 8900,
        'summer_week_1': 5200, 'summer_week_2': 6000,
    }
    assert s['capacity_car'] == 870
    assert s['capacity_motorcycle'] == 6306
    assert s['by_month'] == {'2026-06': 30000}


def test_reproducible_dates_and_ids():
    kw = dict(count=100, seed=23, as_of=DEFAULT_AS_OF)
    a, b = build_demo_data(**kw), build_demo_data(**kw)
    assert a == b


def test_real_area_reference_and_guest_motorcycle_fees():
    from campus_parking_areas import CAR_AREAS, MOTORCYCLE_AREAS
    rows = build_demo_data(count=1000, seed=11, as_of=DEFAULT_AS_OF)
    assert [r['area_name'] for r in rows['parking_area'][:28]] == [x[1] for x in CAR_AREAS]
    assert [r['capacity'] for r in rows['parking_area'][28:]] == [x[2] for x in MOTORCYCLE_AREAS]
    assert rows['parking_area'][0]['area_name'] == '西子灣停車場(來賓)'
    assert validate_small_guest_rules(rows)


def validate_small_guest_rules(rows):
    areas = {a['id']: a for a in rows['parking_area']}
    vehicles = {v['plate_no']: v for v in rows['vehicle']}
    for row in rows['parking_record']:
        area = areas[row['area_ref']]
        vehicle = vehicles.get(row['plate_no'])
        if row['permit_ref'] is None:
            assert area['visitor']
            assert vehicle is None
            if area['vehicle_type'] == 'MOTORCYCLE' and row['exit_time']:
                assert row['parking_fee'] == 0
    return True
