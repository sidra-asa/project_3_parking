"""Read-only analytics APIs backed by the five business entities."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from sqlalchemy import case, extract, func

from app.api.common import APIError, VEHICLE_TYPES, enum, logged_in, parse_date
from app.extensions import db
from app.models import ParkingArea, ParkingPermit, ParkingRecord, Vehicle

bp = Blueprint('analytics_api', __name__, url_prefix='/api/v1/analytics')


def filters():
    """Filter analysis by entry date and vehicle type; Taiwan day boundaries."""
    vehicle_type = request.args.get('vehicle_type')
    if vehicle_type:
        enum(vehicle_type, 'vehicle_type', VEHICLE_TYPES)
    start_s, end_s = request.args.get('start_date'), request.args.get('end_date')
    start = parse_date(start_s, 'start_date') if start_s else None
    end = parse_date(end_s, 'end_date') if end_s else None
    if start and end and start > end:
        raise APIError('start_date 不可晚於 end_date')
    return vehicle_type, start, end


def record_query():
    from datetime import datetime, time, timezone
    vehicle_type, start, end = filters()
    query = db.select(ParkingRecord).join(ParkingArea, ParkingArea.area_id == ParkingRecord.area_id)
    if vehicle_type:
        query = query.where(ParkingArea.vehicle_type == vehicle_type)
    tz = ZoneInfo('Asia/Taipei')
    if start:
        query = query.where(ParkingRecord.entry_time >= datetime.combine(start, time.min, tzinfo=tz))
    if end:
        query = query.where(ParkingRecord.entry_time <
                            datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz))
    return query


@bp.get('/overview')
@logged_in
def overview():
    q = record_query().subquery()
    total = db.session.scalar(db.select(func.count()).select_from(q))
    open_count = db.session.scalar(db.select(func.count()).select_from(q).where(q.c.exit_time.is_(None)))
    closed_q = db.select(q.c.exit_time, q.c.entry_time).where(q.c.exit_time.is_not(None)).subquery()
    if db.engine.dialect.name == 'sqlite':
        # SQLite test fallback: PostgreSQL uses EXTRACT/EPOCH in SQL.
        durations = [(end - start).total_seconds()/60 for end, start in
                     db.session.execute(db.select(closed_q.c.exit_time, closed_q.c.entry_time))]
        avg_minutes = sum(durations)/len(durations) if durations else None
    else:
        avg_minutes = db.session.scalar(db.select(func.avg(
            extract('epoch', closed_q.c.exit_time - closed_q.c.entry_time) / 60)))
    # Current occupancy is real-time and intentionally independent of date filters.
    occupancy_q = db.select(func.count(ParkingRecord.record_id)).where(
        ParkingRecord.exit_time.is_(None))
    vt, _, _ = filters()
    if vt:
        occupancy_q = occupancy_q.join(ParkingArea).where(ParkingArea.vehicle_type == vt)
    occupancy = db.session.scalar(occupancy_q)
    return jsonify(data=dict(total_records=total or 0, open_records_in_period=open_count or 0,
                             currently_parked=occupancy or 0,
                             avg_duration_minutes=round(float(avg_minutes), 1) if avg_minutes is not None else 0))


@bp.get('/by-area')
@logged_in
def by_area():
    q = record_query().subquery()
    stmt = db.select(ParkingArea.area_id, ParkingArea.area_name,
                     ParkingArea.vehicle_type, func.count(q.c.record_id).label('count')).outerjoin(
                     q, ParkingArea.area_id == q.c.area_id).group_by(
                     ParkingArea.area_id, ParkingArea.area_name,
                     ParkingArea.vehicle_type).order_by(ParkingArea.area_id)
    vt, _, _ = filters()
    if vt:
        stmt = stmt.where(ParkingArea.vehicle_type == vt)
    rows = db.session.execute(stmt).all()
    return jsonify(data=[dict(area_id=r.area_id, area_name=r.area_name,
                              vehicle_type=r.vehicle_type, count=r.count) for r in rows])


@bp.get('/by-hour')
@logged_in
def by_hour():
    q = record_query().subquery()
    # Postgres 'timezone' displays the local hour, unlike UTC-based EXTRACT.
    from sqlalchemy import text
    dialect = db.engine.dialect.name
    hour = (extract('hour', func.timezone('Asia/Taipei', q.c.entry_time))
            if dialect == 'postgresql' else extract('hour', q.c.entry_time))
    rows = db.session.execute(db.select(hour.label('hour'),
                                         func.count(q.c.record_id).label('count')).group_by(hour).order_by(hour)).all()
    counts = {int(r.hour): r.count for r in rows}
    return jsonify(data=[dict(hour=h, count=counts.get(h, 0)) for h in range(24)])


@bp.get('/occupancy')
@logged_in
def occupancy():
    # Occupancy always means *now*, not entry counts in a date range.
    vt, _, _ = filters()
    stmt = db.select(ParkingArea.area_id, ParkingArea.area_name, ParkingArea.vehicle_type,
                     ParkingArea.capacity, func.count(ParkingRecord.record_id).label('occupied')).outerjoin(
                     ParkingRecord, (ParkingArea.area_id == ParkingRecord.area_id) &
                     ParkingRecord.exit_time.is_(None)).group_by(
                     ParkingArea.area_id, ParkingArea.area_name,
                     ParkingArea.vehicle_type, ParkingArea.capacity).order_by(ParkingArea.area_id)
    if vt:
        stmt = stmt.where(ParkingArea.vehicle_type == vt)
    return jsonify(data=[dict(area_id=r.area_id, area_name=r.area_name,
                              vehicle_type=r.vehicle_type, capacity=r.capacity,
                              occupied=r.occupied, occupancy_rate=round(r.occupied / r.capacity * 100, 1))
                         for r in db.session.execute(stmt)])


@bp.get('/duration')
@logged_in
def duration():
    q = record_query().subquery()
    rows = db.session.execute(db.select(q.c.entry_time, q.c.exit_time).where(q.c.exit_time.is_not(None)))
    bins = {'<1h': 0, '1-3h': 0, '3-6h': 0, '>=6h': 0}
    for entry, exit_ in rows:
        seconds = (exit_ - entry).total_seconds()
        key = '<1h' if seconds < 3600 else '1-3h' if seconds < 10800 else '3-6h' if seconds < 21600 else '>=6h'
        bins[key] += 1
    return jsonify(data=[dict(duration=key, count=count) for key, count in bins.items()])


@bp.get('/permits')
@logged_in
def permits():
    stmt = db.select(ParkingPermit.academic_year,
                     func.count(ParkingPermit.permit_id).label('issued'),
                     func.sum(case((ParkingPermit.paid_at.is_not(None), 1), else_=0)).label('paid'))
    vt = request.args.get('vehicle_type')
    if vt:
        enum(vt, 'vehicle_type', VEHICLE_TYPES)
        stmt = stmt.join(Vehicle).where(Vehicle.vehicle_type == vt)
    stmt = stmt.group_by(ParkingPermit.academic_year).order_by(ParkingPermit.academic_year)
    return jsonify(data=[dict(academic_year=r.academic_year,
                              issued=r.issued, paid=r.paid) for r in db.session.execute(stmt)])


@bp.get('/revenue')
@logged_in
def revenue():
    # Count actual payments only; permit fees are never joined to parking records.
    from datetime import datetime, time, timezone
    vt, start, end = filters()
    q = db.select(ParkingRecord).join(ParkingArea).where(ParkingRecord.paid_at.is_not(None))
    if vt:
        q = q.where(ParkingArea.vehicle_type == vt)
    tz = ZoneInfo('Asia/Taipei')
    if start:
        q = q.where(ParkingRecord.paid_at >= datetime.combine(start, time.min, tzinfo=tz))
    if end:
        q = q.where(ParkingRecord.paid_at < datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz))
    r = q.subquery()
    stmt = db.select(ParkingArea.area_name,
                     func.coalesce(func.sum(r.c.parking_fee), 0).label('amount'))
    stmt = stmt.select_from(ParkingArea).outerjoin(
        r, r.c.area_id == ParkingArea.area_id).group_by(
        ParkingArea.area_id, ParkingArea.area_name).order_by(ParkingArea.area_id)
    if vt:
        stmt = stmt.where(ParkingArea.vehicle_type == vt)
    rows = db.session.execute(stmt)
    return jsonify(data=[dict(area_name=row.area_name, amount=float(row.amount)) for row in rows])
