from flask import Blueprint, jsonify, request
from flask_login import current_user
from sqlalchemy import or_

from app.api.common import (APIError, commit, get_or_404, must_json,
                            nonempty, pagination, reject_unknown, role_required,
                            search_keyword, search_pattern, search_id)
from app.extensions import db
from app.models import LoginAccount

bp = Blueprint('accounts_api', __name__, url_prefix='/api/v1/accounts')


@bp.get('')
@role_required('ADMIN')
def index():
    query = db.select(LoginAccount)
    if request.args.get('role'):
        role = request.args['role']
        if role not in ('ADMIN', 'VIEWER'):
            raise APIError('role 必須為 ADMIN 或 VIEWER')
        query = query.where(LoginAccount.role == role)
    keyword = search_keyword()
    if keyword:
        pattern = search_pattern(keyword)
        conditions = [LoginAccount.username.ilike(pattern, escape='\\')]
        ident = search_id(keyword)
        if ident is not None:
            conditions.append(LoginAccount.account_id == ident)
        query = query.where(or_(*conditions))
    return pagination(query, LoginAccount, 'account_id')


@bp.get('/<int:pk>')
@role_required('ADMIN')
def show(pk):
    return jsonify(data=get_or_404(LoginAccount, pk).to_dict())


@bp.post('')
@role_required('ADMIN')
def create():
    data = must_json()
    reject_unknown(data, {'username', 'password', 'role'})
    username = nonempty(data.get('username'), 'username', 50)
    password = data.get('password')
    if not isinstance(password, str) or len(password) < 12:
        raise APIError('password 至少需要 12 個字元')
    role = data.get('role', 'VIEWER')
    if role not in ('ADMIN', 'VIEWER'):
        raise APIError('role 必須為 ADMIN 或 VIEWER')
    account = LoginAccount(username=username, role=role, enabled=True)
    account.set_password(password)
    db.session.add(account)
    commit()
    return jsonify(data=account.to_dict()), 201


@bp.patch('/<int:pk>')
@role_required('ADMIN')
def update(pk):
    account = get_or_404(LoginAccount, pk)
    data = must_json()
    reject_unknown(data, {'role', 'is_active', 'password'})
    if not data:
        raise APIError('請提供至少一個可修改欄位')
    if 'role' in data:
        if data['role'] not in ('ADMIN', 'VIEWER'):
            raise APIError('role 必須為 ADMIN 或 VIEWER')
        if pk == current_user.account_id and data['role'] != 'ADMIN':
            raise APIError('不可降低目前登入管理員自己的權限')
        account.role = data['role']
    if 'is_active' in data:
        if not isinstance(data['is_active'], bool):
            raise APIError('is_active 必須為布林值')
        if pk == current_user.account_id and not data['is_active']:
            raise APIError('不可停用自己的帳號')
        account.enabled = data['is_active']
    if 'password' in data:
        if not isinstance(data['password'], str) or len(data['password']) < 12:
            raise APIError('password 至少需要 12 個字元')
        account.set_password(data['password'])
    commit()
    return jsonify(data=account.to_dict())
