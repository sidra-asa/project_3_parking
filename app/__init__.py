import click
from flask import Flask, jsonify, redirect, request, url_for
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import csrf, db, login_manager, migrate
from config import Config


def create_app(test_config=None):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('缺少 SECRET_KEY；請先設定 .env 或環境變數')
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        raise RuntimeError('缺少 DATABASE_URL；請先設定 .env 或環境變數')
    if app.config.get('BEHIND_PROXY'):
        # Trust one reverse proxy only; do not enable on arbitrary exposed deployments.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'web.login'
    migrate.init_app(app, db)

    from app.models import LoginAccount  # noqa: F401

    @login_manager.user_loader
    def load_user(account_id):
        try:
            account = db.session.get(LoginAccount, int(account_id))
        except (ValueError, TypeError):
            return None
        return account if account is not None and account.is_active else None

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith('/api/'):
            return jsonify(error={'code': 'UNAUTHORIZED', 'message': '請先登入'}), 401
        return redirect(url_for('web.login', next=request.path))

    from app.api.common import APIError, error_response

    @app.errorhandler(APIError)
    def on_api_error(e):
        return error_response(e.message, e.status, e.code)

    @app.errorhandler(CSRFError)
    def on_csrf_error(e):
        if request.path.startswith('/api/'):
            return error_response('CSRF 驗證失敗，請重新整理頁面後再試', 400, 'CSRF_FAILED')
        return 'CSRF token invalid', 400

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            return error_response('找不到 API 路徑', 404, 'NOT_FOUND')
        return '404 - 頁面不存在', 404

    from app.web.routes import bp as web_bp
    from app.api.auth import bp as auth_bp
    from app.api.accounts import bp as accounts_bp
    from app.api.resources import bp as resources_bp
    from app.api.records import bp as records_bp
    from app.api.analytics import bp as analytics_bp
    from app.api.analytics_extended import bp as extended_bp
    from app.api.insights import bp as insights_bp

    for bp in (web_bp, auth_bp, accounts_bp, resources_bp, records_bp, analytics_bp, extended_bp, insights_bp):
        app.register_blueprint(bp)

    @app.cli.command('create-admin')
    @click.option('--username', prompt=True, help='登入帳號')
    @click.password_option(help='設定管理員密碼')
    def create_admin(username, password):
        if len(password) < 12:
            raise click.ClickException('密碼至少 12 字元')
        if LoginAccount.query.filter_by(username=username).first():
            raise click.ClickException('帳號已存在')
        acc = LoginAccount(username=username, role='ADMIN', enabled=True)
        acc.set_password(password)
        db.session.add(acc)
        db.session.commit()
        click.echo(f'已建立管理員：{username}')

    from app.services.seed import register_seed_command
    register_seed_command(app)
    return app
