"""Read-only multi-table user profile and management exception queries."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_

from app.api.common import APIError, get_or_404, logged_in, parse_dt, role_required
from app.extensions import db
from app.models import CampusUser, ParkingArea, ParkingPermit, ParkingRecord, Vehicle

bp = Blueprint('insights_api', __name__, url_prefix='/api/v1')
TZ = ZoneInfo('Asia/Taipei')
DEFAULT_AT = datetime(2026, 6, 28, 18, tzinfo=TZ)


@bp.get('/campus-users/<int:user_id>/profile')
@logged_in
def campus_user_profile(user_id):
    person = get_or_404(CampusUser, user_id)
    vehicles = db.session.scalars(db.select(Vehicle).where(Vehicle.user_id == user_id)
                                   .order_by(Vehicle.vehicle_id)).all()
    plates = [v.plate_no for v in vehicles]
    result = dict(user=person.to_dict(), vehicles=[], total_records=0,
                  total_hours=0, favorite_area=None, recent_records=[])
    if not vehicles:
        return jsonify(data=result)
    permits = db.session.scalars(db.select(ParkingPermit).where(
        ParkingPermit.vehicle_id.in_([v.vehicle_id for v in vehicles]))
        .order_by(ParkingPermit.valid_from.desc())).all()
    permit_map = {}
    for p in permits:
        permit_map.setdefault(p.vehicle_id, []).append(p.to_dict())
    for v in vehicles:
        result['vehicles'].append(dict(**v.to_dict(), permits=permit_map.get(v.vehicle_id, [])))
    # ParkingRecord references a plate string, by design: visitor plates have no Vehicle row.
    summary = db.session.execute(db.select(
        func.count(ParkingRecord.record_id),
        func.count(func.distinct(ParkingRecord.plate_no)))
        .where(ParkingRecord.plate_no.in_(plates))).one()
    result['total_records'] = int(summary[0] or 0)
    rows = db.session.execute(db.select(ParkingRecord.entry_time, ParkingRecord.exit_time,
                                        ParkingArea.area_name)
                              .join(ParkingArea).where(ParkingRecord.plate_no.in_(plates))).all()
    area_counts = Counter()
    duration_seconds = 0
    for entry, exit_, area in rows:
        area_counts[area] += 1
        if exit_:
            duration_seconds += (exit_ - entry).total_seconds()
    result['total_hours'] = round(duration_seconds / 3600, 1)
    result['favorite_area'] = area_counts.most_common(1)[0][0] if area_counts else None
    recent = db.session.scalars(db.select(ParkingRecord).where(
        ParkingRecord.plate_no.in_(plates)).order_by(
        ParkingRecord.entry_time.desc(), ParkingRecord.record_id.desc()).limit(20)).all()
    result['recent_records'] = [r.to_dict() for r in recent]
    return jsonify(data=result)


@bp.get('/management/pending')
@role_required('ADMIN')
def pending():
    """Historical as-of lists; no mutation and no claims about today's operations."""
    at = parse_dt(request.args.get('as_of', DEFAULT_AT.isoformat()), 'as_of')
    local_day = at.astimezone(TZ).date()
    # Explicit join path avoids SQLAlchemy's ambiguous-FROM error because
    # ParkingPermit and CampusUser can both be joined to Vehicle.
    unpaid_permits = db.session.execute(db.select(
        ParkingPermit.permit_id, Vehicle.plate_no, CampusUser.name,
        ParkingPermit.academic_year, ParkingPermit.permit_fee)
        .select_from(ParkingPermit)
        .join(Vehicle, ParkingPermit.vehicle_id == Vehicle.vehicle_id)
        .join(CampusUser, Vehicle.user_id == CampusUser.user_id)
        .where(ParkingPermit.paid_at.is_(None), ParkingPermit.valid_from <= local_day,
               ParkingPermit.valid_to >= local_day)
        .order_by(ParkingPermit.permit_id).limit(50)).all()
    unpaid_record_rows = db.session.scalars(db.select(ParkingRecord).where(
        ParkingRecord.exit_time.is_not(None), ParkingRecord.exit_time <= at,
        ParkingRecord.parking_fee > 0, ParkingRecord.paid_at.is_(None))
        .order_by(ParkingRecord.exit_time.desc()).limit(50)).all()
    long_stay_rows = db.session.scalars(db.select(ParkingRecord).where(
        ParkingRecord.entry_time <= at - timedelta(hours=36),
        or_(ParkingRecord.exit_time > at, ParkingRecord.exit_time.is_(None)))
        .order_by(ParkingRecord.entry_time).limit(50)).all()
    def utc(dt):
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    return jsonify(data=dict(
        as_of=at.astimezone(TZ).isoformat(),
        unpaid_permits=[dict(permit_id=p.permit_id, plate_no=p.plate_no,
                             name=p.name, academic_year=p.academic_year,
                             permit_fee=float(p.permit_fee)) for p in unpaid_permits],
        unpaid_records=[p.to_dict() for p in unpaid_record_rows],
        long_stays=[dict(**p.to_dict(), parked_hours=round((at-utc(p.entry_time)).total_seconds()/3600, 1))
                    for p in long_stay_rows],
    ))
