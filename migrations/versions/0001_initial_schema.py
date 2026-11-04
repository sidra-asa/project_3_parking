"""Initial parking miniworld: 5 business tables and 1 login table.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('campus_user',
        sa.Column('user_id',sa.Integer(),primary_key=True),
        sa.Column('name',sa.String(100),nullable=False),
        sa.Column('identity_type',sa.String(20),nullable=False),
        sa.Column('department',sa.String(100),nullable=False),
        sa.Column('phone',sa.String(30)))
    op.create_table('parking_area',
        sa.Column('area_id',sa.Integer(),primary_key=True),
        sa.Column('area_name',sa.String(100),nullable=False),
        sa.Column('vehicle_type',sa.String(20),nullable=False),
        sa.Column('capacity',sa.Integer(),nullable=False),
        sa.Column('hourly_rate',sa.Numeric(8,2),nullable=False),
        sa.CheckConstraint("vehicle_type IN ('CAR', 'MOTORCYCLE')",name='ck_area_vehicle_type'),
        sa.CheckConstraint('capacity > 0',name='ck_area_capacity'),
        sa.CheckConstraint('hourly_rate >= 0',name='ck_area_hourly_rate'))
    op.create_table('login_account',
        sa.Column('account_id',sa.Integer(),primary_key=True),
        sa.Column('username',sa.String(50),nullable=False),
        sa.Column('password_hash',sa.String(255),nullable=False),
        sa.Column('role',sa.String(20),nullable=False),
        sa.Column('is_active',sa.Boolean(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('last_login_at',sa.DateTime(timezone=True)),
        sa.CheckConstraint("role IN ('ADMIN', 'VIEWER')",name='ck_account_role'))
    op.create_index('ix_login_account_username','login_account',['username'],unique=True)
    op.create_table('vehicle',
        sa.Column('vehicle_id',sa.Integer(),primary_key=True),
        sa.Column('plate_no',sa.String(20),nullable=False),
        sa.Column('vehicle_type',sa.String(20),nullable=False),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('campus_user.user_id'),nullable=False),
        sa.CheckConstraint("vehicle_type IN ('CAR', 'MOTORCYCLE')",name='ck_vehicle_type'))
    op.create_index('ix_vehicle_plate_no','vehicle',['plate_no'],unique=True)
    op.create_table('parking_permit',
        sa.Column('permit_id',sa.Integer(),primary_key=True),
        sa.Column('vehicle_id',sa.Integer(),sa.ForeignKey('vehicle.vehicle_id'),nullable=False),
        sa.Column('academic_year',sa.String(10),nullable=False),
        sa.Column('issue_date',sa.Date(),nullable=False),
        sa.Column('valid_from',sa.Date(),nullable=False),
        sa.Column('valid_to',sa.Date(),nullable=False),
        sa.Column('permit_fee',sa.Numeric(10,2),nullable=False),
        sa.Column('payment_method',sa.String(20)),
        sa.Column('paid_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('vehicle_id','academic_year',name='uq_vehicle_academic_year'),
        sa.CheckConstraint('valid_to >= valid_from',name='ck_permit_dates'),
        sa.CheckConstraint('permit_fee >= 0',name='ck_permit_fee'),
        sa.CheckConstraint('(payment_method IS NULL) = (paid_at IS NULL)',name='ck_permit_payment_pair'))
    op.create_table('parking_record',
        sa.Column('record_id',sa.Integer(),primary_key=True),
        sa.Column('plate_no',sa.String(20),nullable=False),
        sa.Column('area_id',sa.Integer(),sa.ForeignKey('parking_area.area_id'),nullable=False),
        sa.Column('permit_id',sa.Integer(),sa.ForeignKey('parking_permit.permit_id')),
        sa.Column('entry_time',sa.DateTime(timezone=True),nullable=False),
        sa.Column('exit_time',sa.DateTime(timezone=True)),
        sa.Column('parking_fee',sa.Numeric(10,2)),
        sa.Column('payment_method',sa.String(20)),
        sa.Column('paid_at',sa.DateTime(timezone=True)),
        sa.CheckConstraint('exit_time IS NULL OR exit_time > entry_time',name='ck_record_time_order'),
        sa.CheckConstraint('parking_fee IS NULL OR parking_fee >= 0',name='ck_record_fee'),
        sa.CheckConstraint('(payment_method IS NULL) = (paid_at IS NULL)',name='ck_record_payment_pair'))
    op.create_index('ix_parking_record_plate_no','parking_record',['plate_no'])
    op.create_index('uq_one_open_record_per_plate','parking_record',['plate_no'],
                    unique=True,postgresql_where=sa.text('exit_time IS NULL'),
                    sqlite_where=sa.text('exit_time IS NULL'))


def downgrade():
    op.drop_index('uq_one_open_record_per_plate',table_name='parking_record')
    op.drop_index('ix_parking_record_plate_no',table_name='parking_record')
    op.drop_table('parking_record')
    op.drop_table('parking_permit')
    op.drop_index('ix_vehicle_plate_no',table_name='vehicle')
    op.drop_table('vehicle')
    op.drop_index('ix_login_account_username',table_name='login_account')
    op.drop_table('login_account')
    op.drop_table('parking_area')
    op.drop_table('campus_user')
