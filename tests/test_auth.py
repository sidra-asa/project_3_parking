def test_unauthenticated_api(client):
    response = client.get('/api/v1/vehicles')
    assert response.status_code == 401


def test_wrong_password(client):
    response = client.post('/api/v1/auth/login', json={'username':'admin','password':'wrong'})
    assert response.status_code == 401


def test_viewer_read_only(viewer):
    assert viewer.get('/api/v1/parking-areas').status_code == 200
    assert viewer.post('/api/v1/parking-areas', json={
        'area_name':'A','vehicle_type':'CAR','capacity':10,'hourly_rate':20
    }).status_code == 403


def test_admin_creates_viewer(admin):
    result = admin.post('/api/v1/accounts',json={
        'username':'teacher','password':'teacher-demo-password','role':'VIEWER'})
    assert result.status_code == 201
    assert 'password_hash' not in result.json['data']


def test_self_demote_rejected(admin):
    assert admin.patch('/api/v1/accounts/1',json={'role':'VIEWER'}).status_code == 400
