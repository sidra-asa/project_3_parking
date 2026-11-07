"""Advanced classroom analytics: period, identity, time-window utilization and permit usage.

No new tables: joins registered plates to their owner and keeps guest plates as
an explicit VISITOR group. All endpoints are read-only and use parameter binds.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from sqlalchemy import case, extract, func, literal, or_, union_all

from app.api.analytics import filters, record_query
from app.api.common import APIError, logged_in, parse_dt
from app.extensions import db
from app.models import CampusUser, ParkingArea, ParkingPermit, ParkingRecord, Vehicle

bp = Blueprint('analytics_extended', __name__, url_prefix='/api/v1/analytics')
TZ = ZoneInfo('Asia/Taipei')
DEMO_START, SUMMER_START, DEMO_END = date(2026, 6, 1), date(2026, 6, 15), date(2026, 6, 28)
DEMO_SNAPSHOT = datetime(2026, 6, 28, 18, tzinfo=TZ)


def _local_day(col):
    if db.engine.dialect.name == 'postgresql':
        return func.date(func.timezone('Asia/Taipei', col))
    return func.date(col, '+8 hours')


def _local_hour(col):
    if db.engine.dialect.name == 'postgresql':
        return extract('hour', func.timezone('Asia/Taipei', col))
    return func.cast(func.strftime('%H', col, '+8 hours'), db.Integer)


def _minutes(entry, exit_):
    """SQL-side elapsed-minute expression, portable for Postgres and SQLite."""
    if db.engine.dialect.name == 'postgresql':
        return extract('epoch', exit_ - entry) / 60
    return (func.julianday(exit_) - func.julianday(entry)) * 1440


def _span(default=True):
    _, start, end = filters()
    if default:
        start = start or DEMO_START
        end = end or DEMO_END
    if start is None or end is None:
        raise APIError('此分析需要 start_date 與 end_date')
    if start > end:
        raise APIError('start_date 不可晚於 end_date')
    if (end - start).days > 365:
        raise APIError('查詢範圍最多 366 天')
    return start, end


def _range_bounds(start, end):
    return (datetime.combine(start, time.min, tzinfo=TZ).astimezone(timezone.utc),
            datetime.combine(end + timedelta(days=1), time.min, tzinfo=TZ).astimezone(timezone.utc))


@bp.get('/daily-trend')
@logged_in
def daily_trend():
    start, end = _span()
    lo, hi = _range_bounds(start, end)
    q = record_query().where(ParkingRecord.entry_time >= lo,
                             ParkingRecord.entry_time < hi).subquery()
    day = _local_day(q.c.entry_time)
    rows = db.session.execute(db.select(day.label('day'), func.count(q.c.record_id))
                              .group_by(day).order_by(day)).all()
    totals = {str(d): count for d, count in rows}
    data = []
    for i in range((end - start).days + 1):
        d = start + timedelta(days=i)
        phase = 'TERM' if d < SUMMER_START else 'SUMMER'
        data.append(dict(date=d.isoformat(), count=totals.get(d.isoformat(), 0),
                         phase=phase, weekend=d.weekday() >= 5))
    return jsonify(data=data)


@bp.get('/by-hour-phase')
@logged_in
def by_hour_phase():
    q = record_query().subquery()
    day = _local_day(q.c.entry_time)
    hour = _local_hour(q.c.entry_time)
    phase = case((day < SUMMER_START, 'TERM'), else_='SUMMER')
    rows = db.session.execute(db.select(phase.label('phase'), hour.label('hour'),
                                        func.count(q.c.record_id)).where(
        day >= DEMO_START, day <= DEMO_END).group_by(phase, hour)).all()
    counts = {(p, int(h)): n for p, h, n in rows}
    return jsonify(data=[dict(hour=h, term=counts.get(('TERM', h), 0),
                              summer=counts.get(('SUMMER', h), 0)) for h in range(24)])


@bp.get('/by-identity')
@logged_in
def by_identity():
    """Classify parking records by current registered vehicle owner; guests remain separate."""
    q = record_query().subquery()
    identity = func.coalesce(CampusUser.identity_type, literal('VISITOR'))
    vt = ParkingArea.vehicle_type
    minutes = _minutes(q.c.entry_time, q.c.exit_time)
    stmt = (db.select(identity.label('identity_type'), vt.label('vehicle_type'),
                      func.count(q.c.record_id).label('trips'),
                      func.count(func.distinct(q.c.plate_no)).label('plates'),
                      func.sum(case((q.c.exit_time.is_not(None), 1), else_=0)).label('closed'),
                      func.avg(case((q.c.exit_time.is_not(None), minutes))).label('duration'))
            .select_from(q).join(ParkingArea, q.c.area_id == ParkingArea.area_id)
            .outerjoin(Vehicle, Vehicle.plate_no == q.c.plate_no)
            .outerjoin(CampusUser, CampusUser.user_id == Vehicle.user_id)
            .group_by(identity, vt).order_by(identity, vt))
    return jsonify(data=[dict(identity_type=r.identity_type, vehicle_type=r.vehicle_type,
                              trips=r.trips, distinct_plates=r.plates, closed_trips=r.closed,
                              avg_duration_hours=round(float(r.duration)/60, 2)
                              if r.duration is not None else 0)
                         for r in db.session.execute(stmt)])


@bp.get('/occupancy-at')
@logged_in
def occupancy_at():
    """Historical occupancy at a timestamp, not at wall-clock now."""
    val = request.args.get('at', DEMO_SNAPSHOT.isoformat())
    at = parse_dt(val, 'at')
    vt, _, _ = filters()
    stmt = (db.select(ParkingArea.area_id, ParkingArea.area_name,
                      ParkingArea.vehicle_type, ParkingArea.capacity,
                      func.count(ParkingRecord.record_id).label('occupied'))
            .select_from(ParkingArea).outerjoin(
                ParkingRecord,
                (ParkingRecord.area_id == ParkingArea.area_id) &
                (ParkingRecord.entry_time <= at) &
                (or_(ParkingRecord.exit_time > at, ParkingRecord.exit_time.is_(None))))
            .group_by(ParkingArea.area_id, ParkingArea.area_name,
                      ParkingArea.vehicle_type, ParkingArea.capacity)
            .order_by(ParkingArea.area_id))
    if vt:
        stmt = stmt.where(ParkingArea.vehicle_type == vt)
    rows = [dict(area_id=r.area_id, area_name=r.area_name, vehicle_type=r.vehicle_type,
                 capacity=r.capacity, occupied=r.occupied,
                 occupancy_rate=round(r.occupied / r.capacity * 100, 1))
            for r in db.session.execute(stmt)]
    return jsonify(data={'at': at.astimezone(TZ).isoformat(),
                         'total_occupied': sum(r['occupied'] for r in rows),
                         'areas': rows})


@bp.get('/area-utilization')
@logged_in
def area_utilization():
    """Exact historical peak occupancy via event deltas + SQL window SUM.

    Trips count arrivals in range; peak occupancy also includes earlier arrivals
    still parked during the selected period. Exit at timestamp t is NOT present
    at t; grouped simultaneous +1/-1 updates ensure that convention.
    """
    start, end = _span()
    lower, upper = _range_bounds(start, end)
    r = ParkingRecord
    # Clip the time interval to the selected window before building events.
    crossing = db.select(r.area_id, r.entry_time, r.exit_time).where(
        r.entry_time < upper, or_(r.exit_time > lower, r.exit_time.is_(None))).subquery()
    entry = case((crossing.c.entry_time < lower, lower), else_=crossing.c.entry_time)
    leave = case((or_(crossing.c.exit_time.is_(None), crossing.c.exit_time > upper), upper),
                 else_=crossing.c.exit_time)
    events = union_all(
        db.select(crossing.c.area_id.label('area_id'), entry.label('moment'), literal(1).label('delta')),
        db.select(crossing.c.area_id.label('area_id'), leave.label('moment'), literal(-1).label('delta'))
    ).subquery()
    grouped = (db.select(events.c.area_id, events.c.moment,
                         func.sum(events.c.delta).label('delta'))
               .group_by(events.c.area_id, events.c.moment).subquery())
    running = db.select(grouped.c.area_id,
                        func.sum(grouped.c.delta).over(
                            partition_by=grouped.c.area_id, order_by=grouped.c.moment
                        ).label('occupancy')).subquery()
    peaks = (db.select(running.c.area_id, func.max(running.c.occupancy).label('peak'))
             .group_by(running.c.area_id).subquery())
    filtered = record_query().where(ParkingRecord.entry_time >= lower,
                                    ParkingRecord.entry_time < upper).subquery()
    trips = (db.select(filtered.c.area_id, func.count(filtered.c.record_id).label('trips'))
             .group_by(filtered.c.area_id).subquery())
    stmt = (db.select(ParkingArea.area_id, ParkingArea.area_name,
                      ParkingArea.vehicle_type, ParkingArea.capacity,
                      func.coalesce(peaks.c.peak, 0).label('peak'),
                      func.coalesce(trips.c.trips, 0).label('trips'))
            .select_from(ParkingArea).outerjoin(peaks, peaks.c.area_id == ParkingArea.area_id)
            .outerjoin(trips, trips.c.area_id == ParkingArea.area_id)
            .order_by(ParkingArea.area_id))
    vt, _, _ = filters()
    if vt:
        stmt = stmt.where(ParkingArea.vehicle_type == vt)
    return jsonify(data=[dict(area_id=r.area_id, area_name=r.area_name,
                              vehicle_type=r.vehicle_type, capacity=r.capacity,
                              arrivals=r.trips, peak_occupied=max(0, int(r.peak)),
                              peak_rate=round(max(0, int(r.peak)) / r.capacity * 100, 1))
                         for r in db.session.execute(stmt)])


@bp.get('/permit-utilization')
@logged_in
def permit_utilization():
    """Includes unused paid permits by LEFT JOIN, unlike INNER JOIN aggregations."""
    start, end = _span()
    lo, hi = _range_bounds(start, end)
    # Counts from records referencing permits during selected entry interval.
    usage = (db.select(ParkingRecord.permit_id.label('permit_id'),
                       func.count(ParkingRecord.record_id).label('trips'))
             .where(ParkingRecord.entry_time >= lo, ParkingRecord.entry_time < hi,
                    ParkingRecord.permit_id.is_not(None))
             .group_by(ParkingRecord.permit_id).subquery())
    stmt = (db.select(ParkingPermit.permit_id, ParkingPermit.academic_year,
                      Vehicle.plate_no, CampusUser.name, CampusUser.identity_type,
                      func.coalesce(usage.c.trips, 0).label('trips'))
            .select_from(ParkingPermit).join(Vehicle).join(CampusUser)
            .outerjoin(usage, usage.c.permit_id == ParkingPermit.permit_id)
            .where(ParkingPermit.paid_at.is_not(None), ParkingPermit.paid_at < hi,
                   ParkingPermit.valid_from <= end,
                   ParkingPermit.valid_to >= start))
    vt, _, _ = filters()
    if vt:
        stmt = stmt.where(Vehicle.vehicle_type == vt)
    counts = defaultdict(int)
    inactive = []
    total, used, visits = 0, 0, 0
    for r in db.session.execute(stmt):
        total += 1
        visits += r.trips
        if r.trips:
            used += 1
        else:
            counts[r.identity_type] += 1
            if len(inactive) < 20:
                inactive.append(dict(permit_id=r.permit_id, plate_no=r.plate_no,
                                     name=r.name, identity_type=r.identity_type,
                                     academic_year=r.academic_year))
    return jsonify(data=dict(issued_paid=total, used=used, unused=total-used,
                             usage_rate=round(used/total*100, 1) if total else 0,
                             visits=visits, unused_by_identity=dict(counts),
                             unused_sample=inactive))
