def test_login_api_rejects_request_without_csrf_when_enabled(app, client):
    app.config['WTF_CSRF_ENABLED'] = True
    response = client.post('/api/v1/auth/login', json={
        'username': 'admin', 'password': 'strong-test-password-1234'})
    assert response.status_code == 400
    assert response.json['error']['code'] == 'CSRF_FAILED'


def test_unauthenticated_html_redirects(client):
    response = client.get('/dashboard')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']
