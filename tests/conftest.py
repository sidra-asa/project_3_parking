"""Isolated SQLite tests; never touches the school's PostgreSQL connection."""
import pytest

@pytest.fixture()
def app(tmp_path):
    pytest.importorskip('flask')
    pytest.importorskip('flask_sqlalchemy')
    from app import create_app
    from app.extensions import db
    from app.models import LoginAccount
    path = tmp_path / 'test.sqlite3'
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': 'testing-secret-only',
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{path}',
        'SQLALCHEMY_ENGINE_OPTIONS': {},
        'WTF_CSRF_ENABLED': False,
        'SESSION_COOKIE_SECURE': False,
    })
    with app.app_context():
        db.create_all()
        for role in ('ADMIN', 'VIEWER'):
            account = LoginAccount(username=role.lower(), role=role, enabled=True)
            account.set_password('strong-test-password-1234')
            db.session.add(account)
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin(client):
    response = client.post('/api/v1/auth/login', json={
        'username': 'admin', 'password': 'strong-test-password-1234'})
    assert response.status_code == 200
    return client


@pytest.fixture()
def viewer(client):
    response = client.post('/api/v1/auth/login', json={
        'username': 'viewer', 'password': 'strong-test-password-1234'})
    assert response.status_code == 200
    return client
