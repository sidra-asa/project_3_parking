from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_user, logout_user

from app.api.common import APIError, commit, logged_in, must_json, nonempty
from app.extensions import db
from app.models import LoginAccount

bp = Blueprint('auth_api', __name__, url_prefix='/api/v1/auth')


@bp.post('/login')
def login():
    data = must_json()
    username = nonempty(data.get('username'), 'username', 50)
    password = data.get('password', '')
    if not isinstance(password, str):
        raise APIError('帳號或密碼錯誤', 401, 'INVALID_CREDENTIALS')
    account = db.session.execute(db.select(LoginAccount).filter_by(username=username)).scalar_one_or_none()
    if not account or not account.is_active or not account.check_password(password):
        raise APIError('帳號或密碼錯誤', 401, 'INVALID_CREDENTIALS')
    login_user(account, fresh=True, remember=False)
    account.last_login_at = datetime.now(timezone.utc)
    commit()
    return jsonify(data=account.to_dict())


@bp.post('/logout')
@logged_in
def logout():
    logout_user()
    return jsonify(data={'message': '已登出'})


@bp.get('/me')
@logged_in
def me():
    return jsonify(data=current_user.to_dict())
