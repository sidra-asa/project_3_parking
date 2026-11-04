"""Reusable JSON API helpers and strict, bounded input parsing."""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps
from zoneinfo import ZoneInfo

from flask import jsonify, request
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db

LOCAL_TZ = ZoneInfo('Asia/Taipei')
VEHICLE_TYPES = {'CAR', 'MOTORCYCLE'}
PAYMENT_METHODS = {'CASH', 'CARD', 'TRANSFER'}
IDENTITY_TYPES = {'STUDENT', 'FACULTY', 'STAFF'}


class APIError(Exception):
    def __init__(self, message, status=400, code='BAD_REQUEST'):
        self.message, self.status, self.code = message, status, code
        super().__init__(message)


def error_response(message, status=400, code='BAD_REQUEST'):
    return jsonify(error={'code': code, 'message': message}), status


def must_json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise APIError('請提供 JSON 物件')
    return data


def nonempty(value, field, length=100):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > length:
        raise APIError(f'{field} 為必填字串，長度上限 {length}')
    return value.strip()


def optional_string(value, field, length=100):
    if value is None or value == '':
        return None
    return nonempty(value, field, length)


def positive_int(value, field, allow_zero=False):
    if isinstance(value, bool):
        raise APIError(f'{field} 必須是整數')
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise APIError(f'{field} 必須是整數') from None
    if str(value).strip() != str(n) or n < (0 if allow_zero else 1):
        raise APIError(f'{field} 必須是有效的正整數')
    return n


def money(value, field):
    try:
        number = Decimal(str(value))
    except (TypeError, InvalidOperation):
        raise APIError(f'{field} 必須是非負數') from None
    if not number.is_finite() or number < 0 or number.as_tuple().exponent < -2:
        raise APIError(f'{field} 必須是非負數且最多兩位小數')
    return number


def enum(value, field, allowed):
    if value not in allowed:
        raise APIError(f'{field} 必須是：{", ".join(sorted(allowed))}')
    return value


def parse_date(value, field):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise APIError(f'{field} 日期格式應為 YYYY-MM-DD') from None


def parse_dt(value, field):
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        raise APIError(f'{field} 時間格式無效') from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc)


def now_utc():
    return datetime.now(timezone.utc)


def local_date(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ).date()


def require_fields(data, *fields):
    missing = [f for f in fields if f not in data]
    if missing:
        raise APIError('缺少欄位：' + ', '.join(missing))


def reject_unknown(data, allowed):
    unknown = set(data) - set(allowed)
    if unknown:
        raise APIError('不支援的欄位：' + ', '.join(sorted(unknown)))


def role_required(role):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                raise APIError('請先登入', 401, 'UNAUTHORIZED')
            if not current_user.is_active:
                raise APIError('帳號已停用', 403, 'FORBIDDEN')
            if current_user.role != role:
                raise APIError('沒有執行此操作的權限', 403, 'FORBIDDEN')
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def logged_in(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            raise APIError('請先登入', 401, 'UNAUTHORIZED')
        return fn(*args, **kwargs)
    return wrapped


def search_keyword():
    """Read a bounded free-text query shared by the list endpoints."""
    keyword = request.args.get('q', '').strip()
    if len(keyword) > 100:
        raise APIError('搜尋關鍵字不可超過 100 個字元')
    return keyword


def search_pattern(keyword):
    """Escape SQL LIKE wildcards so user input is treated as literal text."""
    escaped = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return '%' + escaped + '%'


def search_id(keyword):
    """Return an integer only for ASCII decimal IDs."""
    return int(keyword) if keyword.isascii() and keyword.isdecimal() else None


def pagination(query, model, default_sort):
    page = positive_int(request.args.get('page', 1), 'page')
    per_page = positive_int(request.args.get('per_page', 20), 'per_page')
    per_page = min(per_page, 100)
    sort = request.args.get('sort', default_sort)
    allowed = {c.name for c in model.__table__.columns}
    descending = sort.startswith('-')
    column_name = sort[1:] if descending else sort
    if column_name not in allowed:
        raise APIError('不支援的排序欄位')
    col = getattr(model, column_name)
    query = query.order_by(col.desc() if descending else col.asc())
    result = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return jsonify(data=[item.to_dict() for item in result.items],
                   pagination={'page': page, 'per_page': per_page,
                               'total': result.total, 'pages': result.pages})


def get_or_404(model, pk):
    item = db.session.get(model, pk)
    if item is None:
        raise APIError('找不到指定資料', 404, 'NOT_FOUND')
    return item


def commit():
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        raise APIError('資料違反唯一性或關聯約束，請確認欄位及關聯紀錄', 409, 'CONFLICT') from e
