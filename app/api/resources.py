"""CRUD for campus users, vehicles, parking areas and annual permits."""
from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app.api.common import (
    APIError, IDENTITY_TYPES, VEHICLE_TYPES, PAYMENT_METHODS, commit, enum,
    get_or_404, logged_in, money, must_json, nonempty, optional_string,
    pagination, parse_date, positive_int, reject_unknown, require_fields, role_required,
    now_utc, search_keyword, search_pattern, search_id,
)
from app.extensions import db
from app.models import CampusUser, Vehicle, ParkingArea, ParkingPermit, ParkingRecord

bp = Blueprint('resources_api', __name__, url_prefix='/api/v1')


def _user_fields(obj, data, creating=False):
    fields = {'name', 'identity_type', 'department', 'phone'}
    reject_unknown(data, fields)
    if creating:
        require_fields(data, 'name', 'identity_type', 'department')
    if 'name' in data:
        obj.name = nonempty(data['name'], 'name')
    if 'identity_type' in data:
        obj.identity_type = enum(data['identity_type'], 'identity_type', IDENTITY_TYPES)
    if 'department' in data:
        obj.department = nonempty(data['department'], 'department')
    if 'phone' in data:
        obj.phone = optional_string(data['phone'], 'phone', 30)


def _vehicle_fields(obj, data, creating=False):
    reject_unknown(data, {'plate_no', 'vehicle_type', 'user_id'})
    if creating:
        require_fields(data, 'plate_no', 'vehicle_type', 'user_id')
    if 'plate_no' in data:
        new_plate = nonempty(data['plate_no'], 'plate_no', 20).upper()
        if obj.vehicle_id and obj.plate_no != new_plate and any(p.records for p in obj.permits):
            raise APIError('已有停車歷史的車牌不可修改', 409, 'CONFLICT')
        obj.plate_no = new_plate
    if 'vehicle_type' in data:
        new_type = enum(data['vehicle_type'], 'vehicle_type', VEHICLE_TYPES)
        if obj.vehicle_id and obj.vehicle_type != new_type and obj.permits:
            raise APIError('已存在停車紀錄或停車證時不可變更車種', 409, 'CONFLICT')
        obj.vehicle_type = new_type
    if 'user_id' in data:
        uid = data['user_id']
        obj.user_id = get_or_404(CampusUser, positive_int(uid, 'user_id')).user_id


def _area_fields(obj, data, creating=False):
    reject_unknown(data, {'area_name', 'vehicle_type', 'capacity', 'hourly_rate'})
    if creating:
        require_fields(data, 'area_name', 'vehicle_type', 'capacity', 'hourly_rate')
    if 'area_name' in data:
        obj.area_name = nonempty(data['area_name'], 'area_name')
    if 'vehicle_type' in data:
        new_type = enum(data['vehicle_type'], 'vehicle_type', VEHICLE_TYPES)
        if obj.area_id and obj.vehicle_type != new_type and obj.records:
            raise APIError('已有停車紀錄的區域不可更改車種', 409, 'CONFLICT')
        obj.vehicle_type = new_type
    if 'capacity' in data:
        new_capacity = positive_int(data['capacity'], 'capacity')
        if obj.area_id:
            current = db.session.scalar(db.select(func.count(ParkingRecord.record_id)).where(
                ParkingRecord.area_id == obj.area_id, ParkingRecord.exit_time.is_(None)))
            if current > new_capacity:
                raise APIError('容量不可小於目前停放車輛數', 409, 'CONFLICT')
        obj.capacity = new_capacity
    if 'hourly_rate' in data:
        obj.hourly_rate = money(data['hourly_rate'], 'hourly_rate')


def _permit_fields(obj, data, creating=False):
    writable = {'vehicle_id', 'academic_year', 'issue_date', 'valid_from',
                'valid_to', 'permit_fee'}
    reject_unknown(data, writable)
    if creating:
        require_fields(data, 'vehicle_id', 'academic_year', 'issue_date',
                       'valid_from', 'valid_to', 'permit_fee')
    old_relationship = (obj.vehicle_id, obj.valid_from, obj.valid_to) if obj.permit_id else None
    if 'vehicle_id' in data:
        vid = positive_int(data['vehicle_id'], 'vehicle_id')
        get_or_404(Vehicle, vid)
        if obj.permit_id and obj.vehicle_id != vid and obj.records:
            raise APIError('已被停車紀錄使用的停車證不可更換車輛', 409, 'CONFLICT')
        obj.vehicle_id = vid
    if 'academic_year' in data:
        obj.academic_year = nonempty(data['academic_year'], 'academic_year', 10)
    for field in ('issue_date', 'valid_from', 'valid_to'):
        if field in data:
            setattr(obj, field, parse_date(data[field], field))
    if obj.valid_from is not None and obj.valid_to is not None and obj.valid_to < obj.valid_from:
        raise APIError('valid_to 必須晚於或等於 valid_from')
    if 'permit_fee' in data:
        if obj.permit_id and obj.paid_at is not None:
            raise APIError('已付款停車證不得修改費用', 409, 'CONFLICT')
        obj.permit_fee = money(data['permit_fee'], 'permit_fee')
    if old_relationship and obj.records and old_relationship != (obj.vehicle_id, obj.valid_from, obj.valid_to):
        raise APIError('已使用的停車證不可變更車輛或有效日期', 409, 'CONFLICT')


RESOURCES = {
    'campus-users': (CampusUser, _user_fields, 'user_id'),
    'vehicles': (Vehicle, _vehicle_fields, 'vehicle_id'),
    'parking-areas': (ParkingArea, _area_fields, 'area_id'),
    'parking-permits': (ParkingPermit, _permit_fields, 'permit_id'),
}


def _model(name):
    if name not in RESOURCES:
        raise APIError('無此資料資源', 404, 'NOT_FOUND')
    return RESOURCES[name]


def _filtered_query(name, model):
    query = db.select(model)
    if name == 'vehicles':
        if request.args.get('vehicle_type'):
            vt = enum(request.args['vehicle_type'], 'vehicle_type', VEHICLE_TYPES)
            query = query.where(Vehicle.vehicle_type == vt)
        if request.args.get('plate_no'):
            query = query.where(Vehicle.plate_no.ilike('%' + request.args['plate_no'] + '%'))
    elif name == 'parking-areas':
        if request.args.get('vehicle_type'):
            vt = enum(request.args['vehicle_type'], 'vehicle_type', VEHICLE_TYPES)
            query = query.where(ParkingArea.vehicle_type == vt)
    elif name == 'parking-permits':
        if request.args.get('academic_year'):
            query = query.where(ParkingPermit.academic_year == request.args['academic_year'])
        if request.args.get('vehicle_id'):
            query = query.where(ParkingPermit.vehicle_id == positive_int(request.args['vehicle_id'], 'vehicle_id'))
    elif name == 'campus-users':
        if request.args.get('identity_type'):
            query = query.where(CampusUser.identity_type == enum(
                request.args['identity_type'], 'identity_type', IDENTITY_TYPES))
    keyword = search_keyword()
    if keyword:
        pattern = search_pattern(keyword)
        conditions = []
        ident = search_id(keyword)
        if ident is not None:
            conditions.append(getattr(model, model.__mapper__.primary_key[0].name) == ident)
        if name == 'campus-users':
            conditions.extend((CampusUser.name.ilike(pattern, escape='\\'),
                               CampusUser.department.ilike(pattern, escape='\\'),
                               CampusUser.identity_type.ilike(pattern, escape='\\'),
                               CampusUser.phone.ilike(pattern, escape='\\')))
        elif name == 'vehicles':
            conditions.extend((Vehicle.plate_no.ilike(pattern, escape='\\'),
                               Vehicle.user.has(CampusUser.name.ilike(pattern, escape='\\'))))
        elif name == 'parking-areas':
            conditions.append(ParkingArea.area_name.ilike(pattern, escape='\\'))
        elif name == 'parking-permits':
            conditions.extend((ParkingPermit.academic_year.ilike(pattern, escape='\\'),
                               ParkingPermit.vehicle.has(Vehicle.plate_no.ilike(pattern, escape='\\'))))
        query = query.where(or_(*conditions))
    return query


@bp.get('/<any("campus-users","vehicles","parking-areas","parking-permits"):name>')
@logged_in
def list_resource(name):
    model, _, sort = _model(name)
    return pagination(_filtered_query(name, model), model, sort)


@bp.get('/<any("campus-users","vehicles","parking-areas","parking-permits"):name>/<int:pk>')
@logged_in
def show_resource(name, pk):
    model, _, _ = _model(name)
    return jsonify(data=get_or_404(model, pk).to_dict())


@bp.post('/<any("campus-users","vehicles","parking-areas","parking-permits"):name>')
@role_required('ADMIN')
def create_resource(name):
    model, validator, _ = _model(name)
    if name == 'vehicles':
        raise APIError('請從學年度停車證頁面新增車輛並同時辦證')
    data = must_json()
    new_vehicle = None
    if name == 'parking-permits':
        new_vehicle = data.pop('new_vehicle', None)
        if new_vehicle is not None:
            if 'vehicle_id' in data:
                raise APIError('不可同時指定 vehicle_id 與 new_vehicle')
            if not isinstance(new_vehicle, dict):
                raise APIError('new_vehicle 應為物件')
    item = model()
    try:
        if new_vehicle is not None:
            vehicle = Vehicle()
            _vehicle_fields(vehicle, new_vehicle, creating=True)
            db.session.add(vehicle)
            db.session.flush()
            data['vehicle_id'] = vehicle.vehicle_id
        validator(item, data, creating=True)
        db.session.add(item)
        commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise APIError('車牌重複或資料違反關聯約束', 409, 'CONFLICT') from exc
    except Exception:
        db.session.rollback()
        raise
    return jsonify(data=item.to_dict()), 201


@bp.patch('/<any("campus-users","vehicles","parking-areas","parking-permits"):name>/<int:pk>')
@role_required('ADMIN')
def update_resource(name, pk):
    model, validator, _ = _model(name)
    item = get_or_404(model, pk)
    data = must_json()
    if not data:
        raise APIError('請至少提供一個可修改欄位')
    validator(item, data)
    commit()
    return jsonify(data=item.to_dict())


@bp.delete('/<any("campus-users","vehicles","parking-areas","parking-permits"):name>/<int:pk>')
@role_required('ADMIN')
def delete_resource(name, pk):
    model, _, _ = _model(name)
    item = get_or_404(model, pk)
    # No cascading deletion of historic parking data or accounts.
    if (name == 'campus-users' and item.vehicles or
        name == 'vehicles' and item.permits or
        name == 'parking-areas' and item.records or
        name == 'parking-permits' and item.records):
        raise APIError('此資料已被其他紀錄參照，不可刪除', 409, 'CONFLICT')
    # Removing the last unused permit also removes its Vehicle row, so the
    # registered vehicle list never contains a vehicle without any permit.
    orphan_vehicle = None
    if name == 'parking-permits' and len(item.vehicle.permits) == 1:
        orphan_vehicle = item.vehicle
    db.session.delete(item)
    if orphan_vehicle is not None:
        db.session.delete(orphan_vehicle)
    commit()
    return '', 204


@bp.post('/parking-permits/<int:pk>/pay')
@role_required('ADMIN')
def pay_permit(pk):
    item = get_or_404(ParkingPermit, pk)
    if item.paid_at:
        raise APIError('停車證已經付款', 409, 'CONFLICT')
    data = must_json()
    reject_unknown(data, {'payment_method'})
    method = enum(data.get('payment_method'), 'payment_method', PAYMENT_METHODS)
    item.payment_method = method
    item.paid_at = now_utc()
    commit()
    return jsonify(data=item.to_dict())
