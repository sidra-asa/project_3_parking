from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

bp = Blueprint('web', __name__)


@bp.get('/')
def home():
    return redirect(url_for('web.dashboard' if current_user.is_authenticated else 'web.login'))


@bp.get('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('web.dashboard'))
    return render_template('login.html', title='登入')


@bp.get('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', title='總覽')


RESOURCES = {
    'campus-users': '校內使用者',
    'vehicles': '登記車輛',
    'parking-areas': '停車區域',
    'parking-permits': '學年度停車證',
    'parking-records': '進出場與收費紀錄',
}


@bp.get('/manage/<resource>')
@login_required
def manage(resource):
    if resource == 'accounts':
        if current_user.role != 'ADMIN':
            abort(403)
        return render_template('resource.html', resource=resource, title='網站帳號')
    if resource not in RESOURCES:
        abort(404)
    return render_template('resource.html', resource=resource, title=RESOURCES[resource])


@bp.get('/analysis/extended')
@login_required
def advanced_analytics():
    # Keep the existing route so previously shared links remain valid.
    return render_template('advanced_analytics.html', title='統計分析')


@bp.get('/people/<int:user_id>')
@login_required
def user_profile(user_id):
    return render_template('user_profile.html', title='人員停車資料', user_id=user_id)


@bp.get('/management/review')
@login_required
def management_review():
    if current_user.role != 'ADMIN':
        abort(403)
    return render_template('management_review.html', title='異常與待辦查詢')
