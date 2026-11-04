"""Parking records: arrivals, departures, fee calculation and payment."""
from datetime import timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app.api.common import (APIError, PAYMENT_METHODS, commit, enum, get_or_404,
                            logged_in, must_json, now_utc, pagination, parse_dt, nonempty,
                            positive_int, reject_unknown, role_required,
                            search_keyword, search_pattern, search_id)
from app.extensions import db
from app.models import ParkingArea, ParkingPermit, ParkingRecord
from app.services.parking import (check_area_capacity, check_plate_overlap, price_for_stay,
                                  select_active_permit, validate_permit, validate_plate_area)

bp = Blueprint('records_api', __name__, url_prefix='/api/v1/parking-records')


@bp.get('')
@logged_in
def list_records():
    query = db.select(ParkingRecord)
    for key in ('area_id', 'permit_id'):
        if request.args.get(key):
            query = query.where(getattr(ParkingRecord, key) == positive_int(request.args[key], key))
    if request.args.get('plate_no'):
        query = query.where(ParkingRecord.plate_no == request.args['plate_no'].strip().upper())
    if request.args.get('status'):
        status = request.args['status']
        if status == 'OPEN':
            query = query.where(ParkingRecord.exit_time.is_(None))
        elif status == 'CLOSED':
            query = query.where(ParkingRecord.exit_time.is_not(None))
        else:
            raise APIError('status 必須為 OPEN 或 CLOSED')
    keyword = search_keyword()
    if keyword:
        pattern = search_pattern(keyword)
        conditions = [ParkingRecord.plate_no.ilike(pattern, escape='\\'),
                      ParkingRecord.area.has(ParkingArea.area_name.ilike(pattern, escape='\\'))]
        ident = search_id(keyword)
        if ident is not None:
            conditions.append(ParkingRecord.record_id == ident)
        query = query.where(or_(*conditions))
    return pagination(query, ParkingRecord, '-entry_time')


@bp.get('/<int:pk>')
@logged_in
def show(pk):
    return jsonify(data=get_or_404(ParkingRecord, pk).to_dict())


@bp.post('')
@role_required('ADMIN')
def create():
    data = must_json()
    reject_unknown(data, {'plate_no', 'area_id', 'permit_id', 'entry_time', 'exit_time'})
    plate = nonempty(data.get('plate_no'), 'plate_no', 20).upper()
    area_id = positive_int(data.get('area_id'), 'area_id')
    # Lock the area row on PostgreSQL to serialize simultaneous entries.
    area = db.session.scalar(db.select(ParkingArea).where(
        ParkingArea.area_id == area_id).with_for_update())
    if area is None:
        raise APIError('找不到停車區域', 404, 'NOT_FOUND')
    entered = parse_dt(data['entry_time'], 'entry_time') if data.get('entry_time') else now_utc()
    exited = parse_dt(data['exit_time'], 'exit_time') if data.get('exit_time') else None
    if exited and exited <= entered:
        raise APIError('離場時間必須晚於進場時間')
    if exited and entered > now_utc():
        raise APIError('歷史離場紀錄不可使用未來進場時間')
    check_plate_overlap(plate, entered, exited)
    if exited is None:
        check_area_capacity(area.area_id)
    permit = (get_or_404(ParkingPermit, positive_int(data['permit_id'], 'permit_id'))
              if data.get('permit_id') is not None else select_active_permit(plate, entered))
    if permit:
        validate_permit(permit, plate, entered, exited)
    validate_plate_area(plate, area, permit)
    record = ParkingRecord(plate_no=plate, area_id=area.area_id,
                           permit_id=permit.permit_id if permit else None,
                           entry_time=entered, exit_time=exited,
                           parking_fee=price_for_stay(entered, exited, area.hourly_rate, bool(permit))
                           if exited else None)
    db.session.add(record)
    commit()
    return jsonify(data=record.to_dict()), 201


@bp.patch('/<int:pk>')
@role_required('ADMIN')
def update(pk):
    """Edit the entry time only while vehicle is still present."""
    item = get_or_404(ParkingRecord, pk)
    data = must_json()
    reject_unknown(data, {'entry_time'})
    if 'entry_time' not in data:
        raise APIError('需提供 entry_time')
    if item.exit_time or item.paid_at:
        raise APIError('已離場或已付款的紀錄不得修改進場時間', 409, 'CONFLICT')
    entered = parse_dt(data['entry_time'], 'entry_time')
    if item.permit:
        validate_permit(item.permit, item.plate_no, entered)
    check_plate_overlap(item.plate_no, entered, None, skip_record_id=item.record_id)
    item.entry_time = entered
    commit()
    return jsonify(data=item.to_dict())


@bp.post('/<int:pk>/exit')
@role_required('ADMIN')
def exit_record(pk):
    item = get_or_404(ParkingRecord, pk)
    if item.exit_time:
        raise APIError('車輛已經離場', 409, 'CONFLICT')
    data = must_json()
    reject_unknown(data, {'exit_time'})
    exit_dt = parse_dt(data['exit_time'], 'exit_time') if data.get('exit_time') else now_utc()
    check_plate_overlap(item.plate_no, item.entry_time, exit_dt, skip_record_id=item.record_id)
    if item.permit:
        validate_permit(item.permit, item.plate_no, item.entry_time, exit_dt)
    item.parking_fee = price_for_stay(item.entry_time, exit_dt,
                                      item.area.hourly_rate, bool(item.permit_id))
    item.exit_time = exit_dt
    # Zero-fee records are already settled; no payment entry is required.
    commit()
    return jsonify(data=item.to_dict())


@bp.post('/<int:pk>/pay')
@role_required('ADMIN')
def pay(pk):
    item = get_or_404(ParkingRecord, pk)
    if item.exit_time is None:
        raise APIError('車輛尚未離場，無法結算', 409, 'CONFLICT')
    if item.paid_at:
        raise APIError('已付款', 409, 'CONFLICT')
    if item.parking_fee is None or item.parking_fee == 0:
        raise APIError('此筆紀錄無須付款', 409, 'CONFLICT')
    data = must_json()
    reject_unknown(data, {'payment_method'})
    item.payment_method = enum(data.get('payment_method'), 'payment_method', PAYMENT_METHODS)
    item.paid_at = now_utc()
    commit()
    return jsonify(data=item.to_dict())


@bp.delete('/<int:pk>')
@role_required('ADMIN')
def delete(pk):
    # Only an unpaid, open entry can be cancelled. Keep all historic records.
    item = get_or_404(ParkingRecord, pk)
    if item.exit_time or item.paid_at:
        raise APIError('已離場或已付款紀錄不可刪除', 409, 'CONFLICT')
    db.session.delete(item)
    commit()
    return '', 204
