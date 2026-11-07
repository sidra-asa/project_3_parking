"""Parking flow tests for registered permit vehicles and anonymous guest plates."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from types import SimpleNamespace

import pytest

from app.api.common import APIError
from app.services.parking import validate_permit


def make_area(client, typ='CAR', cap=3, visitor=True):
    name = ('來賓測試停車區' if visitor else '校內測試停車區')
    response = client.post('/api/v1/parking-areas', json={
        'area_name': name, 'vehicle_type': typ, 'capacity': cap, 'hourly_rate': 30
    })
    assert response.status_code == 201, response.json
    return response.json['data']['area_id']


def issue_permit(client, plate='TEST-CAR', typ='CAR', paid=False):
    user = client.post('/api/v1/campus-users', json={
        'name': '測試學生', 'identity_type': 'STUDENT', 'department': '資訊工程學系'
    })
    assert user.status_code == 201
    today = datetime.now(ZoneInfo('Asia/Taipei')).date()
    permit = client.post('/api/v1/parking-permits', json={
        'new_vehicle': {'plate_no': plate, 'vehicle_type': typ,
                        'user_id': user.json['data']['user_id']},
        'academic_year': '115',
        'issue_date': (today-timedelta(days=10)).isoformat(),
        'valid_from': (today-timedelta(days=10)).isoformat(),
        'valid_to': (today+timedelta(days=10)).isoformat(),
        'permit_fee': 500
    })
    assert permit.status_code == 201, permit.json
    result = permit.json['data']
    if paid:
        paid_response = client.post(f"/api/v1/parking-permits/{result['permit_id']}/pay",
                                    json={'payment_method': 'TRANSFER'})
        assert paid_response.status_code == 200, paid_response.json
    return result


def test_guest_stay_does_not_create_vehicle(admin):
    aid = make_area(admin)
    assert admin.get('/api/v1/vehicles').json['pagination']['total'] == 0
    entry = (datetime.now(timezone.utc) - timedelta(hours=1, minutes=5)).isoformat()
    created = admin.post('/api/v1/parking-records', json={
        'plate_no': 'GUEST-001', 'area_id': aid, 'entry_time': entry})
    assert created.status_code == 201, created.json
    rid = created.json['data']['record_id']
    assert created.json['data']['permit_id'] is None
    assert admin.get('/api/v1/vehicles').json['pagination']['total'] == 0
    assert admin.get('/api/v1/campus-users').json['pagination']['total'] == 0
    assert admin.post('/api/v1/parking-records', json={
        'plate_no': 'guest-001', 'area_id': aid}).status_code == 409
    assert admin.get('/api/v1/analytics/occupancy').json['data'][0]['occupied'] == 1
    departed = admin.post(f'/api/v1/parking-records/{rid}/exit', json={})
    assert departed.status_code == 200, departed.json
    assert departed.json['data']['parking_fee'] == 60.0
    assert admin.post(f'/api/v1/parking-records/{rid}/pay', json={
        'payment_method': 'CASH'}).status_code == 200
    assert admin.get('/api/v1/analytics/overview').json['data']['total_records'] == 1
    assert admin.get('/api/v1/analytics/revenue').json['data'][0]['amount'] == 60.0


def test_vehicles_only_created_together_with_permit(admin):
    standalone = admin.post('/api/v1/vehicles', json={
        'plate_no': 'NO-PERMIT', 'vehicle_type': 'CAR', 'user_id': 1})
    assert standalone.status_code == 400
    permit = issue_permit(admin)
    vehicles = admin.get('/api/v1/vehicles').json['data']
    assert len(vehicles) == 1
    assert vehicles[0]['plate_no'] == 'TEST-CAR'
    assert vehicles[0]['permit_status'] in {'UNPAID', 'UPCOMING'}
    # An unused last permit can be removed with its associated vehicle.
    assert admin.delete(f"/api/v1/parking-permits/{permit['permit_id']}").status_code == 204
    assert admin.get('/api/v1/vehicles').json['pagination']['total'] == 0


def test_paid_annual_permit_auto_applied_by_plate(admin):
    aid = make_area(admin, visitor=False)
    permit = issue_permit(admin, paid=True)
    # The permit was just paid; entry must not precede its payment time.
    entry = datetime.now(timezone.utc).isoformat()
    created = admin.post('/api/v1/parking-records', json={
        'plate_no': 'test-car', 'area_id': aid, 'entry_time': entry})
    assert created.status_code == 201, created.json
    assert created.json['data']['permit_id'] == permit['permit_id']
    rid = created.json['data']['record_id']
    departed = admin.post(f'/api/v1/parking-records/{rid}/exit', json={})
    assert departed.status_code == 200, departed.json
    assert departed.json['data']['parking_fee'] == 0
    assert admin.get('/api/v1/analytics/revenue').json['data'][0]['amount'] == 0


def test_nonpermit_must_use_guest_area_and_permit_type_must_match(admin):
    member_area = make_area(admin, 'CAR', visitor=False)
    moto_area = make_area(admin, 'MOTORCYCLE', visitor=False)
    assert admin.post('/api/v1/parking-records', json={
        'plate_no': 'GUEST-002', 'area_id': member_area}).status_code == 409
    issue_permit(admin, paid=True)
    assert admin.post('/api/v1/parking-records', json={
        'plate_no': 'TEST-CAR', 'area_id': moto_area}).status_code == 409


def test_duplicate_plate_and_historical_overlap(admin):
    permit = issue_permit(admin)
    assert admin.post('/api/v1/parking-permits', json={
        'new_vehicle': {'plate_no': 'TEST-CAR', 'vehicle_type': 'CAR', 'user_id': 1},
        'academic_year': '115', 'issue_date': '2026-01-01',
        'valid_from': '2026-01-01', 'valid_to': '2026-12-31',
        'permit_fee': 100
    }).status_code == 409
    aid = make_area(admin)
    base = datetime.now(timezone.utc) - timedelta(days=2)
    one = admin.post('/api/v1/parking-records', json={
        'plate_no': 'ANON-123', 'area_id': aid,
        'entry_time': base.isoformat(), 'exit_time': (base+timedelta(hours=2)).isoformat()})
    assert one.status_code == 201, one.json
    overlap = admin.post('/api/v1/parking-records', json={
        'plate_no': 'ANON-123', 'area_id': aid,
        'entry_time': (base+timedelta(hours=1)).isoformat(),
        'exit_time': (base+timedelta(hours=3)).isoformat()})
    assert overlap.status_code == 409
    adjacent = admin.post('/api/v1/parking-records', json={
        'plate_no': 'ANON-123', 'area_id': aid,
        'entry_time': (base+timedelta(hours=2)).isoformat(),
        'exit_time': (base+timedelta(hours=4)).isoformat()})
    assert adjacent.status_code == 201, adjacent.json


def test_naive_sqlite_paid_at_is_interpreted_as_utc():
    """SQLite drops tzinfo; payment-before-entry must still be enforced."""
    now = datetime.now(timezone.utc)
    permit = SimpleNamespace(
        vehicle=SimpleNamespace(plate_no='TEST-CAR'),
        paid_at=(now - timedelta(minutes=2)).replace(tzinfo=None),
        valid_from=(now - timedelta(days=1)).date(),
        valid_to=(now + timedelta(days=1)).date(),
    )
    validate_permit(permit, 'TEST-CAR', now)
    permit.paid_at = (now + timedelta(minutes=2)).replace(tzinfo=None)
    with pytest.raises(APIError) as exc:
        validate_permit(permit, 'TEST-CAR', now)
    assert exc.value.status == 409
