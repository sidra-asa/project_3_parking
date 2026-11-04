from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.extensions import db


def iso_dt(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class CampusUser(db.Model):
    __tablename__ = 'campus_user'
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    identity_type = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30))
    vehicles = db.relationship('Vehicle', back_populates='user')

    def to_dict(self):
        return dict(user_id=self.user_id, name=self.name,
                    identity_type=self.identity_type, department=self.department,
                    phone=self.phone)


class Vehicle(db.Model):
    __tablename__ = 'vehicle'
    vehicle_id = db.Column(db.Integer, primary_key=True)
    plate_no = db.Column(db.String(20), nullable=False, unique=True, index=True)
    vehicle_type = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('campus_user.user_id'), nullable=False)
    user = db.relationship('CampusUser', back_populates='vehicles')
    permits = db.relationship('ParkingPermit', back_populates='vehicle')
    __table_args__ = (
        db.CheckConstraint("vehicle_type IN ('CAR', 'MOTORCYCLE')", name='ck_vehicle_type'),
    )

    def to_dict(self):
        # A vehicle exists in the register only after a permit has been issued.
        today = datetime.now(ZoneInfo('Asia/Taipei')).date()
        active = next((p for p in self.permits if p.valid_from <= today <= p.valid_to and p.paid_at), None)
        latest = max(self.permits, key=lambda p: (p.valid_from, p.permit_id), default=None)
        status = ('ACTIVE' if active else
                  'UNPAID' if latest and latest.paid_at is None else
                  'UPCOMING' if latest and latest.valid_from > today else
                  'EXPIRED' if latest else 'NONE')
        return dict(vehicle_id=self.vehicle_id, plate_no=self.plate_no,
                    vehicle_type=self.vehicle_type, user_id=self.user_id,
                    user_name=self.user.name if self.user else None,
                    permit_status=status, latest_permit_id=latest.permit_id if latest else None,
                    latest_academic_year=latest.academic_year if latest else None)


class ParkingArea(db.Model):
    __tablename__ = 'parking_area'
    area_id = db.Column(db.Integer, primary_key=True)
    area_name = db.Column(db.String(100), nullable=False)
    vehicle_type = db.Column(db.String(20), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    hourly_rate = db.Column(db.Numeric(8, 2), nullable=False)
    records = db.relationship('ParkingRecord', back_populates='area')
    __table_args__ = (
        db.CheckConstraint("vehicle_type IN ('CAR', 'MOTORCYCLE')", name='ck_area_vehicle_type'),
        db.CheckConstraint('capacity > 0', name='ck_area_capacity'),
        db.CheckConstraint('hourly_rate >= 0', name='ck_area_hourly_rate'),
    )

    def to_dict(self):
        return dict(area_id=self.area_id, area_name=self.area_name,
                    vehicle_type=self.vehicle_type, capacity=self.capacity,
                    hourly_rate=float(self.hourly_rate))


class ParkingPermit(db.Model):
    __tablename__ = 'parking_permit'
    permit_id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.vehicle_id'), nullable=False)
    academic_year = db.Column(db.String(10), nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    valid_from = db.Column(db.Date, nullable=False)
    valid_to = db.Column(db.Date, nullable=False)
    permit_fee = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(20))
    paid_at = db.Column(db.DateTime(timezone=True))
    vehicle = db.relationship('Vehicle', back_populates='permits')
    records = db.relationship('ParkingRecord', back_populates='permit')
    __table_args__ = (
        db.UniqueConstraint('vehicle_id', 'academic_year', name='uq_vehicle_academic_year'),
        db.CheckConstraint('valid_to >= valid_from', name='ck_permit_dates'),
        db.CheckConstraint('permit_fee >= 0', name='ck_permit_fee'),
        db.CheckConstraint('(payment_method IS NULL) = (paid_at IS NULL)', name='ck_permit_payment_pair'),
    )

    def to_dict(self):
        return dict(permit_id=self.permit_id, vehicle_id=self.vehicle_id,
                    plate_no=self.vehicle.plate_no if self.vehicle else None,
                    academic_year=self.academic_year, issue_date=self.issue_date.isoformat(),
                    valid_from=self.valid_from.isoformat(), valid_to=self.valid_to.isoformat(),
                    permit_fee=float(self.permit_fee), payment_method=self.payment_method,
                    paid_at=iso_dt(self.paid_at))


class ParkingRecord(db.Model):
    __tablename__ = 'parking_record'
    record_id = db.Column(db.Integer, primary_key=True)
    plate_no = db.Column(db.String(20), nullable=False, index=True)
    area_id = db.Column(db.Integer, db.ForeignKey('parking_area.area_id'), nullable=False)
    permit_id = db.Column(db.Integer, db.ForeignKey('parking_permit.permit_id'))
    entry_time = db.Column(db.DateTime(timezone=True), nullable=False)
    exit_time = db.Column(db.DateTime(timezone=True))
    parking_fee = db.Column(db.Numeric(10, 2))
    payment_method = db.Column(db.String(20))
    paid_at = db.Column(db.DateTime(timezone=True))
    area = db.relationship('ParkingArea', back_populates='records')
    permit = db.relationship('ParkingPermit', back_populates='records')
    __table_args__ = (
        db.CheckConstraint('exit_time IS NULL OR exit_time > entry_time', name='ck_record_time_order'),
        db.CheckConstraint('parking_fee IS NULL OR parking_fee >= 0', name='ck_record_fee'),
        db.CheckConstraint('(payment_method IS NULL) = (paid_at IS NULL)', name='ck_record_payment_pair'),
        # A guest plate has no Vehicle row, so enforce uniqueness on the plate itself.
        db.Index('uq_one_open_record_per_plate', 'plate_no', unique=True,
                 postgresql_where=db.text('exit_time IS NULL'),
                 sqlite_where=db.text('exit_time IS NULL')),
    )

    def to_dict(self):
        return dict(record_id=self.record_id, plate_no=self.plate_no,
                    vehicle_type=self.area.vehicle_type if self.area else None,
                    area_id=self.area_id, area_name=self.area.area_name if self.area else None,
                    permit_id=self.permit_id, entry_time=iso_dt(self.entry_time),
                    exit_time=iso_dt(self.exit_time), parking_fee=float(self.parking_fee)
                    if self.parking_fee is not None else None,
                    payment_method=self.payment_method, paid_at=iso_dt(self.paid_at))


# Separate from CampusUser, because website operators are not necessarily campus people.
from app.models.login_account import LoginAccount  # noqa: E402,F401
