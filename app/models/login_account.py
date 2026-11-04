from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import iso_dt


class LoginAccount(UserMixin, db.Model):
    __tablename__ = 'login_account'
    account_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='VIEWER')
    enabled = db.Column('is_active', db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (
        db.CheckConstraint("role IN ('ADMIN', 'VIEWER')", name='ck_account_role'),
    )

    @property
    def is_active(self):
        return self.enabled

    def get_id(self):
        return str(self.account_id)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return dict(account_id=self.account_id, username=self.username,
                    role=self.role, is_active=self.enabled,
                    created_at=iso_dt(self.created_at),
                    last_login_at=iso_dt(self.last_login_at))
