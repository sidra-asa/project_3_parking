"""Deterministic, fictional NSYSU-style parking demo for the database course.

This is not an official university dataset. Area labels/capacities are imported
from the existing project file; population, permits, arrivals and fees are
illustrative. No database connection is made by this module.

Scenario: 2026-06-01 through 2026-06-28 (114 academic year), including
regular classes, final exams, summer vacation and the Dragon Boat holiday.
All 30,000 *entries* are on or before the 2026-06-28 18:00 +08:00 snapshot.
A trip still parked at that instant has exit_time=None, rather than being
added later as an unrelated synthetic open-stay record.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
import heapq
import math
import random
from zoneinfo import ZoneInfo

from campus_parking_areas import (
    CAR_AREAS, MOTORCYCLE_AREAS, CAR_VISITOR_NUMBERS,
    MOTORCYCLE_VISITOR_NUMBERS, CAR_STUDENT_PERMIT_NUMBERS,
)

TAIPEI = ZoneInfo('Asia/Taipei')
START_DATE = date(2026, 6, 1)
END_DATE = date(2026, 6, 28)
DEFAULT_AS_OF = datetime(2026, 6, 28, 18, 0, tzinfo=TAIPEI)
HOLIDAYS = frozenset({date(2026, 6, 19)})
# Weekly proportions, deliberately NOT observed NSYSU traffic statistics.
WEEKLY_SHARES = (9900, 8900, 5200, 6000)
USER_COUNTS = {'STUDENT': 11330, 'FACULTY': 740, 'STAFF': 930}
PERMIT_COUNTS = {'CAR': 2033, 'MOTORCYCLE': 4608}

STUDENT_DEPARTMENTS = (
    '中國文學系', '外國語文學系', '音樂學系', '劇場藝術學系',
    '資訊工程學系', '電機工程學系', '機械與機電工程學系',
    '材料與光電科學學系', '光電工程學系', '化學系', '物理學系',
    '應用數學系', '生物科學系', '企業管理學系', '財務管理學系',
    '資訊管理學系', '政治經濟學系', '社會學系', '中國與亞太區域研究所',
    '海洋科學系', '海洋環境及工程學系', '海洋生物科技暨資源學系',
)
OFFICE_DEPARTMENTS = (
    '教務處', '學生事務處', '總務處', '研究發展處', '國際事務處',
    '圖書與資訊處', '人事室', '主計室', '秘書室', '校務研究辦公室',
)


def _as_utc(dt):
    return dt.astimezone(timezone.utc)


def _price(start, end, hourly_rate, permit_ref):
    if permit_ref is not None:
        return Decimal('0.00')
    hours = (Decimal(str((end - start).total_seconds())) / Decimal(3600)).to_integral_value(
        rounding=ROUND_CEILING)
    return (hours * hourly_rate).quantize(Decimal('0.01'))


def _make_areas():
    areas = []
    for no, name, spaces in CAR_AREAS:
        areas.append(dict(id=len(areas) + 1, area_name=name, vehicle_type='CAR',
                          capacity=spaces, hourly_rate=Decimal(50 if no == 1 else 30),
                          map_no=no, visitor=no in CAR_VISITOR_NUMBERS,
                          popularity=1.4 if no in (1, 4, 9, 23) else 1.0))
    for no, name, spaces in MOTORCYCLE_AREAS:
        areas.append(dict(id=len(areas) + 1, area_name=name,
                          vehicle_type='MOTORCYCLE', capacity=spaces,
                          hourly_rate=Decimal(0), map_no=no,
                          visitor=no in MOTORCYCLE_VISITOR_NUMBERS,
                          popularity=1.3 if no in (1, 2, 5, 8, 13, 16, 17) else 1.0))
    return areas


def _make_users(rng):
    surnames = '陳林黃張李王吳劉蔡楊許鄭謝郭洪曾邱廖賴周'
    first = '子承雅家柏冠志怡佳品俊思宇宥書韋庭宏彥慧'
    second = '廷安晴蓉翔寧萱偉豪穎柔恩涵潔軒妤澤欣'
    users = []
    for typ, size in USER_COUNTS.items():
        departments = OFFICE_DEPARTMENTS if typ == 'STAFF' else STUDENT_DEPARTMENTS
        for _ in range(size):
            users.append(dict(id=len(users) + 1,
                              name=rng.choice(surnames) + rng.choice(first) + rng.choice(second),
                              identity_type=typ, department=rng.choice(departments), phone=None))
    return users


def _make_vehicles(rng, users):
    students = [u['id'] for u in users if u['identity_type'] == 'STUDENT']
    staff = [u['id'] for u in users if u['identity_type'] != 'STUDENT']
    assigned = Counter()
    vehicles = []
    # About one car in ten is registered to a student. Employees may have two
    # registered vehicles, but no user has more than three in this Miniworld.
    for typ, n in PERMIT_COUNTS.items():
        for k in range(1, n + 1):
            student = rng.random() < (0.11 if typ == 'CAR' else 0.87)
            pool = students if student else staff
            owner = rng.choice(pool)
            while assigned[owner] >= 3:
                owner = rng.choice(pool)
            assigned[owner] += 1
            vehicles.append(dict(id=len(vehicles) + 1,
                                 plate_no=f'DEMO-{"C" if typ == "CAR" else "M"}-{k:05d}',
                                 vehicle_type=typ, user_ref=owner))
    return vehicles


def _make_permits(rng, vehicles, users):
    types = {u['id']: u['identity_type'] for u in users}
    begin, end = date(2025, 11, 1), date(2026, 10, 31)
    permits = []
    for v in vehicles:
        owner_type = types[v['user_ref']]
        fee = Decimal('300.00') if v['vehicle_type'] == 'MOTORCYCLE' else (
            Decimal('600.00') if owner_type == 'STUDENT' else Decimal('1000.00'))
        issue = begin - timedelta(days=rng.randint(12, 70))
        if rng.random() < 0.06:
            issue = begin + timedelta(days=rng.randint(1, 110))
        is_paid = rng.random() < 0.985
        paid_day = issue + timedelta(days=rng.randint(0, 7))
        paid_at = _as_utc(datetime.combine(
            paid_day, time(rng.randint(9, 18), rng.randrange(60)), tzinfo=TAIPEI)) if is_paid else None
        permits.append(dict(id=len(permits) + 1, vehicle_ref=v['id'],
                            academic_year='114', issue_date=issue,
                            valid_from=begin, valid_to=end, permit_fee=fee,
                            payment_method=rng.choice(('CARD', 'TRANSFER')) if is_paid else None,
                            paid_at=paid_at))
    return permits


def _phase(day):
    if day <= date(2026, 6, 7):
        return 'classes'
    if day <= date(2026, 6, 14):
        return 'exams'
    if day <= date(2026, 6, 21):
        return 'summer_week_1'
    return 'summer_week_2'


def _allocate_weighted(total, weights):
    if total == 0:
        return [0] * len(weights)
    mass = sum(weights)
    exact = [total * x / mass for x in weights]
    base = [int(x) for x in exact]
    for j in sorted(range(len(weights)), key=lambda i: (exact[i] - base[i], -i), reverse=True)[:total - sum(base)]:
        base[j] += 1
    return base


def _daily_counts(total, snapshot):
    # Keep week-by-week mix stable when count is changed via --records.
    weeks = _allocate_weighted(total, WEEKLY_SHARES)
    out = {}
    for index, week_total in enumerate(weeks):
        days = [START_DATE + timedelta(days=index * 7 + d) for d in range(7)]
        weights = []
        for day in days:
            if day > snapshot.date():
                weights.append(0)
            elif day in HOLIDAYS:
                weights.append(0.38)
            elif day.weekday() >= 5:
                weights.append(0.38 if index < 2 else 0.47)
            else:
                weights.append(1.0)
        for day, n in zip(days, _allocate_weighted(week_total, weights)):
            out[day] = n
    return out


def _user_profiles(rng, vehicles, users):
    by_id = {u['id']: u for u in users}
    profiles = {}
    for v in vehicles:
        u = by_id[v['user_ref']]
        typ = u['identity_type']
        dorm = typ == 'STUDENT' and v['vehicle_type'] == 'MOTORCYCLE' and rng.random() < 0.17
        weekdays = tuple(sorted(rng.sample(range(5), rng.randint(3, 5) if typ != 'STUDENT'
                                           else rng.randint(2, 5))))
        if dorm:
            arrival = rng.choice((10, 13, 17, 19))
        elif typ == 'STAFF':
            arrival = rng.choice((7, 8, 8, 8, 9))
        elif typ == 'FACULTY':
            arrival = rng.choice((8, 9, 10, 11, 13))
        else:
            arrival = rng.choice((8, 8, 9, 10, 13, 14))
        profiles[v['id']] = dict(identity=typ, department=u['department'],
                                 weekdays=weekdays, arrival=arrival, dorm=dorm,
                                 energy=rng.uniform(0.6, 1.4))
    return profiles


def _dept_zone(department):
    if any(s in department for s in ('資訊', '電機', '光電', '機械', '材料', '理工', '物理', '化學', '數學')):
        return 'engineering'
    if any(s in department for s in ('海洋', '海工', '海科', '海資')):
        return 'marine'
    if any(s in department for s in ('企業', '財務', '管理', '政治', '社會', '亞太')):
        return 'management'
    if any(s in department for s in ('文學', '中文', '外國', '音樂', '劇場', '藝術')):
        return 'arts'
    return 'administration'


ZONE_AREAS = {
    'CAR': {
        'engineering': (7, 9, 10, 11), 'marine': (18, 19, 20, 21, 22, 23),
        'management': (12, 13, 14, 15), 'arts': (24, 25, 26, 27),
        'administration': (5, 6, 16, 17),
    },
    'MOTORCYCLE': {
        'engineering': (1, 5, 7, 8), 'marine': (9, 10, 12),
        'management': (1, 5, 7, 8), 'arts': (13, 14, 15),
        'administration': (1, 3, 5, 7),
    },
}


def _candidate_order(rng, pool, profiles, day, phase, visitor):
    # Weighted permutation without replacement: recurring drivers are more
    # likely to appear on familiar weekdays. Never assigns the same vehicle
    # twice in a day. Results remain reproducible for a given RNG seed.
    ranking = []
    for vehicle in pool:
        if visitor:
            weight = (1.9 if vehicle['regular_guest'] else 0.65)
            if day.weekday() >= 5:
                weight *= 1.15
        else:
            prof = profiles[vehicle['id']]
            weight = prof['energy']
            if day.weekday() < 5:
                weight *= 3.1 if day.weekday() in prof['weekdays'] else 0.18
            elif prof['dorm']:
                weight *= 0.5
            else:
                weight *= 0.20 if prof['identity'] == 'STUDENT' else 0.10
            if phase.startswith('summer') and prof['identity'] == 'STUDENT':
                weight *= 0.22 if not prof['dorm'] else 0.45
            if phase == 'exams' and prof['identity'] == 'STUDENT':
                weight *= 0.80
            if vehicle['vehicle_type'] == 'CAR' and prof['identity'] == 'STUDENT':
                weight *= 0.22  # student permit cars share only the 65-space seaside lot
            if prof['dorm']:
                weight *= 0.27  # few arrivals, but very long occupancy
        score = -math.log(max(rng.random(), 1e-12)) / max(weight, 0.001)
        ranking.append((score, vehicle['id'], vehicle))
    ranking.sort(key=lambda item: (item[0], item[1]))
    return [v for _, _, v in ranking]


def _arrival(rng, day, visitor, profile, snapshot):
    if visitor:
        h = rng.choices((8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18),
                        weights=(1, 2, 5, 7, 8, 9, 9, 8, 5, 3, 1), k=1)[0]
    elif profile['dorm']:
        h = max(7, min(21, round(rng.gauss(profile['arrival'], 2.0))))
    else:
        h = max(6, min(21, round(rng.gauss(profile['arrival'], 0.85))))
        if day.weekday() >= 5:
            h = max(8, h)
    minute = rng.randrange(60)
    entered = _as_utc(datetime.combine(day, time(h, minute), tzinfo=TAIPEI))
    if entered > snapshot:
        # June 28 has a fixed 18:00 snapshot: no post-snapshot arrivals.
        entered = _as_utc(datetime.combine(day, time(rng.randint(9, 17), minute), tzinfo=TAIPEI))
    return entered


def _stay_minutes(rng, vehicle_type, visitor, profile, day, phase):
    if visitor:
        return rng.randint(35, 260) if vehicle_type == 'CAR' else rng.randint(25, 250)
    if profile['dorm']:
        return rng.randint(2 * 24 * 60, 7 * 24 * 60)
    if profile['identity'] == 'STAFF':
        return rng.randint(450, 620) if day.weekday() < 5 else rng.randint(80, 260)
    if profile['identity'] == 'FACULTY':
        return rng.randint(280, 630) if day.weekday() < 5 else rng.randint(90, 320)
    if phase == 'exams':
        return rng.randint(100, 330)
    if phase.startswith('summer'):
        return rng.randint(140, 450)
    return rng.randint(180, 520)


def build_demo_data(*, count=30000, active_count=None, seed=20261103, as_of=None):
    """Five in-memory tables. `active_count` is deprecated; open stays emerge
    from actual simulated trips crossing `as_of`, not an independent batch.
    """
    if not isinstance(count, int) or count <= 0:
        raise ValueError('count must be a positive integer')
    if active_count is not None:
        raise ValueError('--active is no longer supported; open stays are derived at the snapshot')
    snapshot = as_of if as_of is not None else DEFAULT_AS_OF
    if snapshot.tzinfo is None:
        raise ValueError('as_of must include a timezone')
    snapshot = _as_utc(snapshot)
    if snapshot.astimezone(TAIPEI).date() != END_DATE:
        raise ValueError('as_of must fall on 2026-06-28 (the final simulated day)')
    if not time(18, 0) <= snapshot.astimezone(TAIPEI).time() <= time(23, 59, 59):
        raise ValueError('as_of must be between 18:00 and 23:59 Taiwan time')

    rng = random.Random(seed)
    users, areas = _make_users(rng), _make_areas()
    vehicles = _make_vehicles(rng, users)
    permits = _make_permits(rng, vehicles, users)
    profiles = _user_profiles(rng, vehicles, users)
    paid = {p['vehicle_ref']: p for p in permits if p['paid_at'] is not None}
    guest_vehicles = []
    for typ, size in (('CAR', 2400), ('MOTORCYCLE', 3400)):
        for n in range(1, size + 1):
            guest_vehicles.append(dict(id=f'G{typ[0]}-{n}',
                                       plate_no=f'DEMO-G{typ[0]}-{n:05d}',
                                       vehicle_type=typ, user_ref=None,
                                       regular_guest=n <= round(size * 0.12)))
    pools = {}
    for typ in ('CAR', 'MOTORCYCLE'):
        pools[(typ, False)] = [v for v in vehicles if v['vehicle_type'] == typ and v['id'] in paid]
        pools[(typ, True)] = [v for v in guest_vehicles if v['vehicle_type'] == typ]

    areas_by_kind = {}
    for typ in ('CAR', 'MOTORCYCLE'):
        for visitor in (False, True):
            areas_by_kind[(typ, visitor)] = [a for a in areas if a['vehicle_type'] == typ
                                               and a['visitor'] == visitor]
    area_exits = {a['id']: [] for a in areas}
    last_vehicle_exit = {}
    last_user_exit = {}
    favorite = {}
    records = []
    daily_targets = _daily_counts(count, snapshot.astimezone(TAIPEI))

    # Build candidates day-by-day; then process in global chronological order.
    # Each vehicle is sampled at most once per day; multi-day dorm stays are
    # excluded again while actual arrivals are processed.
    proposed = []
    day_backups = {}
    for day in sorted(daily_targets):
        n = daily_targets[day]
        phase = _phase(day)
        weekend = day.weekday() >= 5 or day in HOLIDAYS
        grouped = defaultdict(int)
        for _ in range(n):
            v_rate = (0.59 if weekend else (0.13 if phase == 'classes' else
                      0.15 if phase == 'exams' else 0.27))
            visitor = rng.random() < v_rate
            car_rate = 0.60 if visitor else (0.45 if phase.startswith('summer') else 0.34)
            typ = 'CAR' if rng.random() < car_rate else 'MOTORCYCLE'
            grouped[(typ, visitor)] += 1
        for (typ, visitor), slots in sorted(grouped.items()):
            pool = pools[(typ, visitor)]
            if slots > len(pool):
                raise ValueError('daily demand exceeds the eligible driver pool; lower --records')
            order = _candidate_order(rng, pool, profiles, day, phase, visitor)
            key = (day, typ, visitor)
            day_backups[key] = iter(order[slots:])
            for vehicle in order[:slots]:
                entry = _arrival(rng, day, visitor, profiles.get(vehicle['id']), snapshot)
                proposed.append((entry, rng.random(), day, typ, visitor, vehicle))
    proposed.sort(key=lambda t: (t[0], t[1]))

    for entry, _, day, typ, visitor, candidate in proposed:
        backup = day_backups[(day, typ, visitor)]
        vehicle = candidate
        while (last_vehicle_exit.get(vehicle['plate_no'], datetime.min.replace(tzinfo=timezone.utc)) > entry or
               (vehicle['user_ref'] is not None and
                last_user_exit.get(vehicle['user_ref'], datetime.min.replace(tzinfo=timezone.utc)) > entry)):
            try:
                vehicle = next(backup)
            except StopIteration as exc:
                raise RuntimeError(f'No available {typ} driver on {day}; reduce the record count') from exc
        permit = None if visitor else paid[vehicle['id']]
        profile = profiles.get(vehicle['id'])
        duration = _stay_minutes(rng, typ, visitor, profile, day, _phase(day))
        actual_exit = entry + timedelta(minutes=duration)
        # Permit is valid for the entire trip; a 114-school-year stay will not
        # cross its October expiry in this June scenario.
        if permit is not None:
            assert permit['paid_at'] <= entry and permit['valid_from'] <= day <= permit['valid_to']
        if visitor:
            options = areas_by_kind[(typ, True)]
        elif typ == 'CAR' and profile['identity'] == 'STUDENT':
            options = [a for a in areas if a['vehicle_type'] == 'CAR'
                       and a['map_no'] in CAR_STUDENT_PERMIT_NUMBERS]
        else:
            options = areas_by_kind[(typ, False)]

        for area in options:
            heap = area_exits[area['id']]
            while heap and heap[0] <= entry:
                heapq.heappop(heap)
        available = [a for a in options if len(area_exits[a['id']]) < a['capacity']]
        if not available:
            raise RuntimeError(f'All eligible {typ} lots are full at {entry}; reduce peak demand')
        key = vehicle['plate_no']
        if key not in favorite:
            zone = _dept_zone(profile['department']) if profile else 'administration'
            fav_zone = ZONE_AREAS[typ][zone] if not visitor else ()
            candidates = [a for a in options if a['map_no'] in fav_zone] or options
            if visitor and typ == 'CAR':
                candidates = [a for a in options if a['map_no'] in (1, 3)] or options
            favorite[key] = rng.choices(candidates,
                                        weights=[a['capacity'] ** 0.5 * a['popularity'] for a in candidates],
                                        k=1)[0]['id']
        preferred = next((a for a in available if a['id'] == favorite[key]), None)
        if preferred is not None and rng.random() < 0.83:
            area = preferred
        else:
            area = rng.choices(available, weights=[a['capacity'] ** 0.55 * a['popularity']
                                                    for a in available], k=1)[0]
        still_open = actual_exit > snapshot
        fee = None if still_open else _price(entry, actual_exit, area['hourly_rate'],
                                              None if permit is None else permit['id'])
        payment_method, paid_at = None, None
        if fee is not None and fee > 0:
            paid_at = actual_exit - timedelta(minutes=min(duration - 1, rng.randint(3, 12)))
            payment_method = rng.choices(('CARD', 'CASH', 'TRANSFER'),
                                         weights=(52, 37, 11), k=1)[0]
        records.append(dict(id=len(records) + 1, plate_no=vehicle['plate_no'],
                            area_ref=area['id'], permit_ref=None if permit is None else permit['id'],
                            entry_time=entry, exit_time=None if still_open else actual_exit,
                            parking_fee=fee, payment_method=payment_method, paid_at=paid_at))
        last_vehicle_exit[key] = actual_exit
        if vehicle['user_ref'] is not None:
            last_user_exit[vehicle['user_ref']] = actual_exit
        heapq.heappush(area_exits[area['id']], actual_exit)

    if len(records) != count:
        raise AssertionError('the requested record count was not generated')
    return dict(campus_user=users, vehicle=vehicles, parking_area=areas,
                parking_permit=permits, parking_record=records)


def summarize_dataset(rows, as_of=DEFAULT_AS_OF):
    records, areas = rows['parking_record'], rows['parking_area']
    by_area = {a['id']: a['vehicle_type'] for a in areas}
    months = Counter(r['entry_time'].astimezone(TAIPEI).strftime('%Y-%m') for r in records)
    dates = Counter(r['entry_time'].astimezone(TAIPEI).strftime('%Y-%m-%d') for r in records)
    weeks = Counter(_phase(r['entry_time'].astimezone(TAIPEI).date()) for r in records)
    vehicle_types = Counter(by_area[r['area_ref']] for r in records)
    hours = Counter(r['entry_time'].astimezone(TAIPEI).hour for r in records)
    identities = Counter(u['identity_type'] for u in rows['campus_user'])
    return dict(
        scenario='NSYSU-style 114 school year: classes / exams / summer (fictional)',
        start_date=START_DATE.isoformat(), end_date=END_DATE.isoformat(),
        as_of=as_of.isoformat(),
        campus_users=len(rows['campus_user']), by_identity=dict(identities),
        vehicles=len(rows['vehicle']),
        permits=len(rows['parking_permit']),
        permits_by_vehicle_type={typ: sum(v['vehicle_type'] == typ for v in rows['vehicle'])
                                 for typ in ('CAR', 'MOTORCYCLE')},
        areas=len(areas), area_car=sum(a['vehicle_type'] == 'CAR' for a in areas),
        area_motorcycle=sum(a['vehicle_type'] == 'MOTORCYCLE' for a in areas),
        capacity_car=sum(a['capacity'] for a in areas if a['vehicle_type'] == 'CAR'),
        capacity_motorcycle=sum(a['capacity'] for a in areas if a['vehicle_type'] == 'MOTORCYCLE'),
        records=len(records), closed_records=sum(r['exit_time'] is not None for r in records),
        active_records=sum(r['exit_time'] is None for r in records),
        by_month=dict(sorted(months.items())), by_date=dict(sorted(dates.items())),
        by_phase=dict(sorted(weeks.items())), by_vehicle_type=dict(sorted(vehicle_types.items())),
        peak_hours=hours.most_common(5),
        visitor_records=sum(r['permit_ref'] is None for r in records),
        permit_records=sum(r['permit_ref'] is not None for r in records),
        paid_visitor_records=sum(r['paid_at'] is not None for r in records),
        free_motorcycle_visits=sum(r['parking_fee'] == 0 and r['permit_ref'] is None
                                   and by_area[r['area_ref']] == 'MOTORCYCLE' for r in records),
    )
