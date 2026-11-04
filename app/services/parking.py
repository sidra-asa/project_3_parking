"""Parking rules for permits and anonymous visitor stays."""
from datetime import timezone
from decimal import Decimal, ROUND_CEILING

from sqlalchemy import func, or_
from app.api.common import APIError, local_date
from app.extensions import db
from app.models import ParkingArea, ParkingPermit, ParkingRecord, Vehicle


def select_active_permit(plate_no, entered_at):
    day = local_date(entered_at)
    return db.session.scalar(db.select(ParkingPermit).join(Vehicle).where(
        Vehicle.plate_no == plate_no,
        ParkingPermit.valid_from <= day,
        ParkingPermit.valid_to >= day,
        ParkingPermit.paid_at.is_not(None),
        ParkingPermit.paid_at <= entered_at,
    ).order_by(ParkingPermit.permit_id.desc()).limit(1))


def validate_permit(permit, plate_no, entry_dt, exit_dt=None):
    if permit.vehicle.plate_no != plate_no:
        raise APIError('停車證與車牌不相符', 409, 'CONFLICT')
    if not permit.paid_at or permit.paid_at > entry_dt:
        raise APIError('停車證於進場時尚未付款', 409, 'CONFLICT')
    first_day = local_date(entry_dt)
    last_day = local_date(exit_dt) if exit_dt else first_day
    if not (permit.valid_from <= first_day and last_day <= permit.valid_to):
        raise APIError('停車證在此停車期間無效', 409, 'CONFLICT')


def price_for_stay(entry, exit_, hourly_rate, has_permit=False):
    if entry.tzinfo is None:
        entry = entry.replace(tzinfo=timezone.utc)
    if exit_.tzinfo is None:
        exit_ = exit_.replace(tzinfo=timezone.utc)
    if exit_ <= entry:
        raise APIError('離場時間必須晚於進場時間')
    if has_permit:
        return Decimal('0.00')
    seconds = Decimal(str((exit_ - entry).total_seconds()))
    hours = (seconds / Decimal(3600)).to_integral_value(rounding=ROUND_CEILING)
    return (hours * hourly_rate).quantize(Decimal('0.01'))


def check_area_capacity(area_id):
    occupied = db.session.scalar(db.select(func.count(ParkingRecord.record_id)).where(
        ParkingRecord.area_id == area_id, ParkingRecord.exit_time.is_(None)))
    area = db.session.get(ParkingArea, area_id)
    if occupied >= area.capacity:
        raise APIError('停車區域已達容量上限', 409, 'CONFLICT')


def validate_plate_area(plate_no, area, permit):
    if permit is not None:
        if permit.vehicle.vehicle_type != area.vehicle_type:
            raise APIError('停車證車種與停車區域不相符', 409, 'CONFLICT')
    else:
        # For guest stays the area determines vehicle type; no Vehicle row is created.
        # Campus reference lots are named with '(來賓)'; custom lots can use this suffix.
        if '來賓' not in area.area_name and '訪客' not in area.area_name:
            raise APIError('無有效停車證者，請選擇來賓停車區域', 409, 'CONFLICT')


def check_plate_overlap(plate_no, entered, exited=None, skip_record_id=None):
    # Interval intersection: existing entry < new exit AND existing exit > new entry.
    # Open exit denotes +infinity; this also rejects overlapping historical records.
    stmt = db.select(ParkingRecord.record_id).where(ParkingRecord.plate_no == plate_no)
    if exited is not None:
        stmt = stmt.where(ParkingRecord.entry_time < exited)
    stmt = stmt.where(or_(ParkingRecord.exit_time.is_(None), ParkingRecord.exit_time > entered))
    if skip_record_id is not None:
        stmt = stmt.where(ParkingRecord.record_id != skip_record_id)
    if db.session.scalar(stmt.limit(1)) is not None:
        raise APIError('同一車牌的停車時間不可重疊', 409, 'CONFLICT')
