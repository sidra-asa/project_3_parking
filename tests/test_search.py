"""List searches run in SQL before pagination, including anonymous guest plates."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def _user(client, name, department, identity='STUDENT', phone=None):
    r = client.post('/api/v1/campus-users', json={
        'name': name, 'department': department, 'identity_type': identity, 'phone': phone})
    assert r.status_code == 201
    return r.json['data']['user_id']


def _registered_vehicle(client, plate, kind, user_id=None):
    if user_id is None:
        user_id = _user(client, '示範車主', '資訊工程學系')
    today = datetime.now(ZoneInfo('Asia/Taipei')).date()
    r = client.post('/api/v1/parking-permits', json={
        'new_vehicle': {'plate_no': plate, 'vehicle_type': kind, 'user_id': user_id},
        'academic_year': '115', 'issue_date': today.isoformat(),
        'valid_from': today.isoformat(),
        'valid_to': (today+timedelta(days=30)).isoformat(), 'permit_fee': 100})
    assert r.status_code == 201, r.json
    return r.json['data']['vehicle_id'], r.json['data']['permit_id']


def _area(client, name, kind):
    r = client.post('/api/v1/parking-areas', json={
        'area_name': name, 'vehicle_type': kind, 'capacity': 20, 'hourly_rate': 30})
    assert r.status_code == 201
    return r.json['data']['area_id']


def _search(client, resource, **params):
    r = client.get(f'/api/v1/{resource}', query_string=params)
    assert r.status_code == 200, r.json
    return r.json


def test_user_search_before_pagination(admin):
    for i in range(25):
        _user(admin, f'示範{i}', '其他系所')
    target = _user(admin, '王小明', '資訊工程學系', phone='0912345678')
    assert _search(admin,'campus-users',q='王小明',per_page=20)['data'][0]['user_id']==target
    assert _search(admin,'campus-users',q='資訊工程',identity_type='STUDENT')['pagination']['total']==1


def test_registered_vehicle_and_permit_search(admin):
    owner = _user(admin, '張老師', '電機工程學系', identity='FACULTY')
    vid, pid = _registered_vehicle(admin, 'NSYSU-123', 'CAR', owner)
    _registered_vehicle(admin, 'NSYSU-456', 'MOTORCYCLE')
    area = _area(admin, '西子灣停車場(來賓)', 'CAR')
    assert _search(admin,'vehicles',q='sysu-123')['data'][0]['vehicle_id']==vid
    assert _search(admin,'vehicles',q='張老師')['pagination']['total']==1
    assert _search(admin,'vehicles',q='NSYSU',vehicle_type='CAR')['pagination']['total']==1
    assert _search(admin,'parking-permits',q='NSYSU-123')['data'][0]['permit_id']==pid
    assert _search(admin,'parking-areas',q='西子灣')['data'][0]['area_id']==area


def test_guest_plate_search_without_vehicle(admin):
    area = _area(admin, '海堤停車場(來賓)', 'CAR')
    created = admin.post('/api/v1/parking-records', json={
        'plate_no': 'GUEST-8989', 'area_id': area,
        'entry_time': (datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()})
    assert created.status_code == 201, created.json
    rid = created.json['data']['record_id']
    assert _search(admin,'vehicles',q='GUEST-8989')['pagination']['total']==0
    assert _search(admin,'parking-records',q='guest-89',status='OPEN')['data'][0]['record_id']==rid
    assert _search(admin,'parking-records',q='海堤')['pagination']['total']==1
    assert _search(admin,'parking-records',q=str(rid))['pagination']['total']>=1
    assert _search(admin,'parking-records',q='GUEST-8989',status='CLOSED')['pagination']['total']==0


def test_literal_wildcards_and_query_bounds(admin):
    _area(admin, '百分比100%停車場', 'CAR')
    _area(admin, '一般停車場', 'CAR')
    _area(admin, '地下_A區', 'CAR')
    assert _search(admin, 'parking-areas', q='%')['pagination']['total']==1
    assert _search(admin, 'parking-areas', q='_')['pagination']['total']==1
    assert admin.get('/api/v1/parking-records',query_string={'q':'x'*101}).status_code==400


def test_account_search_admin_only(admin):
    assert _search(admin, 'accounts', q='viewer',role='VIEWER')['pagination']['total']==1
    assert admin.post('/api/v1/auth/logout', json={}).status_code==200
    assert admin.post('/api/v1/auth/login',json={
        'username':'viewer','password':'strong-test-password-1234'}).status_code==200
    assert admin.get('/api/v1/accounts').status_code==403
