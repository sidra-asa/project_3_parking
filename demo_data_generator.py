"""Reproducible synthetic NSYSU-style parking activity; Python stdlib only.

Real-world reference: only the parking-area labels/capacities come from the
115-02-23 NSYSU map supplied for the course. Vehicles, users, stay histories,
traffic demand, permit assignments and simplified hourly rates are SYNTHETIC.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
import heapq
import random
from zoneinfo import ZoneInfo

from campus_parking_areas import (
    CAR_AREAS, MOTORCYCLE_AREAS, CAR_VISITOR_NUMBERS,
    MOTORCYCLE_VISITOR_NUMBERS, CAR_STUDENT_PERMIT_NUMBERS,
)

TAIPEI = ZoneInfo('Asia/Taipei')
START_DATE = date(2026, 5, 1)
END_DATE = date(2026, 10, 31)
# These demand weights are illustrative. No real counts have been published.
MONTH_WEIGHT = {5: 1.00, 6: 1.05, 7: 0.40, 8: 0.47, 9: 1.18, 10: 1.30}
# Only dates explicitly recorded on the 115 academic calendar are included.
FALL_HOLIDAYS = {date(2026, 9, 25), date(2026, 9, 28),
                 date(2026, 10, 9), date(2026, 10, 26)}


def _as_utc(local_dt):
    return local_dt.astimezone(timezone.utc)


def _price(start, end, hourly_rate, permit_ref):
    if permit_ref is not None:
        return Decimal('0.00')
    secs = Decimal(str((end - start).total_seconds()))
    hours = (secs / Decimal(3600)).to_integral_value(rounding=ROUND_CEILING)
    return (hours * hourly_rate).quantize(Decimal('0.01'))


def _make_areas():
    result = []
    for no, name, spaces in CAR_AREAS:
        # Simplified school-project rate, NOT the university fee table.
        rate = 50 if no == 1 else 30
        result.append(dict(id=len(result) + 1, area_name=name, vehicle_type='CAR',
                           capacity=spaces, hourly_rate=Decimal(rate),
                           map_no=no, visitor=(no in CAR_VISITOR_NUMBERS),
                           popularity=1.45 if no in (1, 4, 9, 23, 28) else 1.0))
    for no, name, spaces in MOTORCYCLE_AREAS:
        # School visitor motorcycle parking is free. Permitted campus use also
        # incurs no per-stay charge under this project Miniworld.
        result.append(dict(id=len(result) + 1, area_name=name, vehicle_type='MOTORCYCLE',
                           capacity=spaces, hourly_rate=Decimal('0'),
                           map_no=no, visitor=(no in MOTORCYCLE_VISITOR_NUMBERS),
                           popularity=1.45 if no in (1, 2, 5, 8, 13, 16, 17) else 1.0))
    return result


def _make_users(rng):
    surnames = '陳林黃張李王吳劉蔡楊許鄭謝郭洪曾邱廖賴周'
    first = '子承雅家柏冠志怡佳品俊思宇宥書韋庭宏彥慧'
    second = '廷安晴蓉翔寧萱偉豪穎柔恩涵潔軒妤澤欣'
    student_depts = ('資訊工程學系', '電機工程學系', '企業管理學系',
                     '海洋科學系', '機械與機電工程學系', '政治經濟學系',
                     '應用數學系', '中國文學系', '化學系')
    office_depts = ('總務處', '教務處', '圖書與資訊處', '學務處', '管理學院')
    users = []
    for i in range(1, 1501):
        typ = 'STUDENT' if i <= 1050 else 'FACULTY' if i <= 1275 else 'STAFF'
        dept = rng.choice(student_depts if typ != 'STAFF' else office_depts)
        name = rng.choice(surnames) + rng.choice(first) + rng.choice(second)
        users.append(dict(id=i, name=name, identity_type=typ, department=dept, phone=None))
    return users


def _make_vehicles(rng, users):
    """Applicant vehicles only. Unpermitted guests never enter this table."""
    students = [u['id'] for u in users if u['identity_type'] == 'STUDENT']
    employees = [u['id'] for u in users if u['identity_type'] != 'STUDENT']
    vehicles = []
    # Offer sufficient applicants for 200 car + 400 motorcycle permits per year.
    # Unselected applicants are removed after issuing the permits.
    for i in range(1, 1051):
        typ = 'CAR' if i <= 350 else 'MOTORCYCLE'
        n = i if typ == 'CAR' else i - 350
        if typ == 'CAR':
            owners = employees if rng.random() < 0.70 else students
        else:
            owners = students if rng.random() < 0.83 else employees
        owner = rng.choice(owners)
        plate = f'DEMO-{"C" if typ == "CAR" else "M"}-{n:04d}'
        vehicles.append(dict(id=i, plate_no=plate, vehicle_type=typ, user_ref=owner))
    return vehicles


def _make_permits(rng, vehicles, users):
    user_type = {u['id']: u['identity_type'] for u in users}
    car = [v for v in vehicles if v['vehicle_type'] == 'CAR' and v['user_ref']]
    moto = [v for v in vehicles if v['vehicle_type'] == 'MOTORCYCLE' and v['user_ref']]
    # A subset renew for 115, so recurring commuting patterns span school years.
    old_car, old_moto = [], []
    result = []
    for yr, start, end in [
        ('114', date(2025, 11, 1), date(2026, 10, 31)),
        ('115', date(2026, 11, 1), date(2027, 10, 31)),
    ]:
        def choose(pool, previous, n):
            keep = rng.sample(previous, min(len(previous), n // 2)) if previous else []
            chosen = {v['id'] for v in previous}
            remainder = rng.sample([v for v in pool if v['id'] not in chosen], n - len(keep))
            return keep + remainder
        old_car = choose(car, old_car, 200)
        old_moto = choose(moto, old_moto, 400)
        for v in old_car + old_moto:
            owner_type = user_type[v['user_ref']]
            fee = Decimal('300.00') if v['vehicle_type'] == 'MOTORCYCLE' else (
                Decimal('600.00') if owner_type == 'STUDENT' else Decimal('1000.00'))
            # Issue/payment preceding the annual-validity start date.
            issue = start - timedelta(days=rng.randint(20, 65))
            # Include a handful of applications not yet paid, for admin screens.
            paid = rng.random() < 0.97
            payment_time = _as_utc(datetime.combine(
                issue + timedelta(days=rng.randint(0, 7)), time(12, 0), tzinfo=TAIPEI))
            result.append(dict(id=len(result) + 1, vehicle_ref=v['id'],
                               academic_year=yr, issue_date=issue,
                               valid_from=start, valid_to=end, permit_fee=fee,
                               payment_method=rng.choice(('CARD', 'TRANSFER')) if paid else None,
                               paid_at=payment_time if paid else None))
    return result


def _day_weight(d):
    w = MONTH_WEIGHT[d.month]
    if d.weekday() >= 5:
        w *= 0.56
    if d in FALL_HOLIDAYS:
        w *= 0.52
    if date(2026, 9, 1) <= d < date(2026, 9, 7):
        w *= 0.66  # 115/9/7: start of classes
    return w


def _choose_hour(rng, weekend, visitor):
    # Weekend leisure and weekday commuter arrivals have distinct peaks.
    if visitor:
        weights = [0.03] * 24
        for h, w in ((8, 0.8), (9, 1.4), (10, 3.5), (11, 4.2),
                     (12, 3.6), (13, 4.8), (14, 4.1), (15, 3.7),
                     (16, 2.6), (17, 1.5), (18, 1.1), (19, 0.5)):
            weights[h] = w
    elif weekend:
        weights = [0.06] * 24
        for h, w in ((7, 0.5), (8, 1.3), (9, 2.0), (10, 2.5),
                     (11, 2.4), (12, 2.1), (13, 2.9), (14, 2.3),
                     (15, 1.6), (16, 1.3), (17, 1.2), (18, 0.7)):
            weights[h] = w
    else:
        weights = [0.03] * 24
        for h, w in ((6, 0.5), (7, 2.6), (8, 8.0), (9, 6.4),
                     (10, 2.7), (11, 1.3), (12, 2.1), (13, 4.3),
                     (14, 2.4), (15, 1.0), (16, 0.7), (17, 0.9),
                     (18, 0.5), (19, 0.3), (20, 0.2)):
            weights[h] = w
    return rng.choices(range(24), weights=weights, k=1)[0]


def _stay_minutes(rng, typ, visitor, owner_type, weekend):
    if visitor:
        return rng.randint(35, 230) if typ == 'CAR' else rng.randint(25, 290)
    if typ == 'CAR':
        if weekend:
            return rng.randint(80, 300)
        return rng.randint(410, 630) if owner_type != 'STUDENT' else rng.randint(180, 470)
    # Dormitory-oriented scooter stays sometimes extend across midnight.
    p = rng.random()
    if owner_type == 'STUDENT' and p < 0.08:
        return rng.randint(11 * 60, 35 * 60)
    if weekend:
        return rng.randint(90, 340)
    return rng.randint(180, 570) if owner_type == 'STUDENT' else rng.randint(380, 610)


def build_demo_data(*, count=30000, active_count=450, seed=20261103, as_of=None):
    """Return five in-memory tables; 30k records includes 450 open by default."""
    if count <= 0 or not 0 <= active_count <= min(count, 2600):
        raise ValueError('count must be positive and active_count within available vehicles')
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('as_of needs an explicit timezone')
    now = now.astimezone(timezone.utc)
    local_now = now.astimezone(TAIPEI)
    if not date(2026, 11, 1) <= local_now.date() <= date(2027, 10, 31):
        raise ValueError('as_of must be in 115 permit year (2026-11-01..2027-10-31)')

    rng = random.Random(seed)
    users = _make_users(rng)
    areas = _make_areas()
    applicants = _make_vehicles(rng, users)
    permits = _make_permits(rng, applicants, users)
    issued_vehicle_ids = {p['vehicle_ref'] for p in permits}
    vehicles = [v for v in applicants if v['id'] in issued_vehicle_ids]
    # Anonymous guest traffic uses plate strings only, with no Vehicle/User rows.
    guest_vehicles = [
        dict(id=f'G{typ[0]}-{i}', plate_no=f'DEMO-G{typ[0]}-{i:04d}',
             vehicle_type=typ, user_ref=None)
        for typ, n in (('CAR', 600), ('MOTORCYCLE', 1100))
        for i in range(1, n + 1)
    ]
    user_type = {u['id']: u['identity_type'] for u in users}
    permits_by_vehicle = {}
    for p in permits:
        permits_by_vehicle.setdefault(p['vehicle_ref'], []).append(p)

    def permit_at(v, enter, leave):
        entry_d = enter.astimezone(TAIPEI).date()
        final_d = (leave or enter).astimezone(TAIPEI).date()
        for p in permits_by_vehicle.get(v['id'], ()):
            if (p['paid_at'] and p['paid_at'] <= enter and
                    p['valid_from'] <= entry_d and final_d <= p['valid_to']):
                return p['id']
        return None

    pools = {t: [v for v in vehicles if v['vehicle_type'] == t]
             for t in ('CAR', 'MOTORCYCLE')}
    guest_pools = {t: [v for v in guest_vehicles if v['vehicle_type'] == t]
                   for t in ('CAR', 'MOTORCYCLE')}
    # A consistent habitual choice for each driver, selected lazily per
    # (vehicle, permit/visitor) category, never overruling access eligibility.
    preferred_areas = {}
    last_exit = {}
    area_exits = {a['id']: [] for a in areas}
    records = []

    def permitted_areas(v, permit_id):
        if permit_id is None:
            if v['vehicle_type'] == 'CAR':
                return [a for a in areas if a['vehicle_type'] == 'CAR' and a['visitor']]
            return [a for a in areas if a['vehicle_type'] == 'MOTORCYCLE' and a['visitor']]
        if v['vehicle_type'] == 'MOTORCYCLE':
            return [a for a in areas if a['vehicle_type'] == 'MOTORCYCLE' and not a['visitor']]
        owner = user_type[v['user_ref']]
        if owner == 'STUDENT':
            return [a for a in areas if a['vehicle_type'] == 'CAR' and
                    a['map_no'] in CAR_STUDENT_PERMIT_NUMBERS]
        return [a for a in areas if a['vehicle_type'] == 'CAR' and not a['visitor']]

    def pick_vehicle(typ, enter, want_permit):
        pool = pools[typ] if want_permit else guest_pools[typ]
        for _ in range(100):
            v = rng.choice(pool)
            if ((permit_at(v, enter, None) is not None) == want_permit and
                    last_exit.get(v['id'], datetime.min.replace(tzinfo=timezone.utc)) <= enter):
                return v
        choices = [v for v in pool if
                   (permit_at(v, enter, None) is not None) == want_permit and
                   last_exit.get(v['id'], datetime.min.replace(tzinfo=timezone.utc)) <= enter]
        if not choices:
            raise RuntimeError(f'No eligible available {typ} vehicle for {enter}')
        return rng.choice(choices)

    def pick_area(v, permit_id, enter):
        possible = permitted_areas(v, permit_id)
        for a in possible:
            heap = area_exits[a['id']]
            while heap and heap[0] <= enter:
                heapq.heappop(heap)
        free = [a for a in possible if len(area_exits[a['id']]) < a['capacity']]
        if not free:
            raise RuntimeError(f'All eligible areas are occupied at {enter}')
        key = (v['id'], permit_id is not None)
        fav = preferred_areas.get(key)
        if fav is None:
            fav = rng.choices(possible, weights=[a['capacity'] ** 0.55 *
                                a['popularity'] for a in possible], k=1)[0]['id']
            preferred_areas[key] = fav
        if rng.random() < 0.77:
            for a in free:
                if a['id'] == fav:
                    return a
        return rng.choices(free, weights=[a['capacity'] ** 0.55 *
                           a['popularity'] for a in free], k=1)[0]

    days = [START_DATE + timedelta(days=k) for k in range((END_DATE - START_DATE).days + 1)]
    daily = rng.choices(days, weights=[_day_weight(d) for d in days], k=count - active_count)
    proposed = []
    for d in daily:
        weekend = d.weekday() >= 5 or d in FALL_HOLIDAYS
        # Visitor share rises on weekends; campus-member commuting shrinks in summer.
        visitor_chance = (0.59 if weekend else 0.24)
        if d.month in (7, 8):
            visitor_chance += 0.12
        visitor = rng.random() < visitor_chance
        typ = rng.choices(('CAR', 'MOTORCYCLE'), weights=(30, 70), k=1)[0]
        hour = _choose_hour(rng, weekend, visitor)
        entered = _as_utc(datetime.combine(d, time(hour, rng.randrange(60)), tzinfo=TAIPEI))
        proposed.append((entered, typ, not visitor, weekend))
    proposed.sort(key=lambda item: item[0])

    for entered, typ, want_permit, weekend in proposed:
        v = pick_vehicle(typ, entered, want_permit)
        owner_type = user_type.get(v['user_ref'])
        mins = _stay_minutes(rng, typ, not want_permit, owner_type, weekend)
        left = entered + timedelta(minutes=mins)
        permit_id = permit_at(v, entered, left)
        # If a permit holder enters late on 10/31 and leaves on 11/01,
        # shorten this synthetic visit before the permit expires.
        if want_permit and permit_id is None:
            permit_on_entry = permit_at(v, entered, None)
            if permit_on_entry is None:
                raise RuntimeError('Cannot find paid permit on entry')
            current = next(p for p in permits_by_vehicle[v['id']]
                           if p['id'] == permit_on_entry)
            expiry = _as_utc(datetime.combine(current['valid_to'] + timedelta(days=1),
                                               time.min, tzinfo=TAIPEI))
            left = min(left, expiry - timedelta(seconds=1))
            if left <= entered:
                raise RuntimeError('No time available before permit expiration')
            permit_id = permit_at(v, entered, left)
            if permit_id is None:
                raise RuntimeError('Cannot find a permit covering whole stay')
        area = pick_area(v, permit_id, entered)
        fee = _price(entered, left, area['hourly_rate'], permit_id)
        paid = fee > 0 and rng.random() < 0.96
        records.append(dict(id=len(records) + 1, plate_no=v['plate_no'],
                            area_ref=area['id'], permit_ref=permit_id,
                            entry_time=entered, exit_time=left, parking_fee=fee,
                            payment_method=rng.choices(('CARD', 'CASH', 'TRANSFER'),
                                                       weights=(48, 42, 10), k=1)[0] if paid else None,
                            paid_at=left + timedelta(minutes=rng.randint(2, 15)) if paid else None))
        last_exit[v['id']] = left
        heapq.heappush(area_exits[area['id']], left)

    # An independent current snapshot (still capacity & access constrained).
    # Scale was explicitly chosen for a teaching dashboard; it is NOT a census.
    n_car = round(active_count * 0.30)
    types = ['CAR'] * n_car + ['MOTORCYCLE'] * (active_count - n_car)
    rng.shuffle(types)
    for typ in types:
        # At 18:00 commuter stays remain, and visitor lots stay active.
        want_permit = rng.random() < (0.58 if typ == 'CAR' else 0.68)
        entered = now - timedelta(minutes=rng.randint(25, 560))
        v = pick_vehicle(typ, entered, want_permit)
        permit_id = permit_at(v, entered, None)
        area = pick_area(v, permit_id, entered)
        records.append(dict(id=len(records) + 1, plate_no=v['plate_no'],
                            area_ref=area['id'], permit_ref=permit_id,
                            entry_time=entered, exit_time=None, parking_fee=None,
                            payment_method=None, paid_at=None))
        # Active stay has no exit; use far future to block any subsequent picks.
        last_exit[v['id']] = datetime.max.replace(tzinfo=timezone.utc)
        heapq.heappush(area_exits[area['id']], datetime.max.replace(tzinfo=timezone.utc))

    assert len(records) == count
    return dict(campus_user=users, vehicle=vehicles, parking_area=areas,
                parking_permit=permits, parking_record=records)


def summarize_dataset(rows):
    records = rows['parking_record']
    areas = rows['parking_area']
    area_type = {a['id']: a['vehicle_type'] for a in areas}
    months = Counter(r['entry_time'].astimezone(TAIPEI).strftime('%Y-%m') for r in records)
    by_type = Counter(area_type[r['area_ref']] for r in records)
    by_hour = Counter(r['entry_time'].astimezone(TAIPEI).hour for r in records)
    return dict(
        campus_users=len(rows['campus_user']), vehicles=len(rows['vehicle']),
        permits=len(rows['parking_permit']), areas=len(areas),
        area_car=sum(a['vehicle_type'] == 'CAR' for a in areas),
        area_motorcycle=sum(a['vehicle_type'] == 'MOTORCYCLE' for a in areas),
        capacity_car=sum(a['capacity'] for a in areas if a['vehicle_type'] == 'CAR'),
        capacity_motorcycle=sum(a['capacity'] for a in areas if a['vehicle_type'] == 'MOTORCYCLE'),
        records=len(records), closed_records=sum(r['exit_time'] is not None for r in records),
        active_records=sum(r['exit_time'] is None for r in records),
        by_month=dict(sorted(months.items())),
        by_vehicle_type=dict(sorted(by_type.items())),
        peak_hours=by_hour.most_common(5),
        visitor_records=sum(r['permit_ref'] is None for r in records),
        permit_records=sum(r['permit_ref'] is not None for r in records),
        paid_visitor_records=sum(r['paid_at'] is not None for r in records),
        free_motorcycle_visits=sum(r['parking_fee'] == 0 and r['permit_ref'] is None
                                   and area_type[r['area_ref']] == 'MOTORCYCLE'
                                   for r in records),
    )
