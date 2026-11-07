"""DB migration smoke tests requiring SQLAlchemy/Alembic, not Flask."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_initial_migration_has_guest_plate_not_vehicle_fk():
    sa = pytest.importorskip('sqlalchemy')
    pytest.importorskip('alembic')
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    engine = sa.create_engine('sqlite:///:memory:')
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        op = Operations(context)
        path = ROOT / 'migrations/versions/0001_initial_schema.py'
        spec = spec_from_file_location('initial_parking_schema', path)
        migration = module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.op = op
        migration.upgrade()

        inspector = sa.inspect(connection)
        assert len(inspector.get_table_names()) == 6
        rec_columns = {c['name'] for c in inspector.get_columns('parking_record')}
        assert 'plate_no' in rec_columns
        assert 'vehicle_id' not in rec_columns
        vehicle_owner = next(c for c in inspector.get_columns('vehicle') if c['name'] == 'user_id')
        assert vehicle_owner['nullable'] is False
        indexes = {x['name']: x for x in inspector.get_indexes('parking_record')}
        assert indexes['uq_one_open_record_per_plate']['unique']

        connection.execute(sa.text("INSERT INTO parking_area (area_id,area_name,vehicle_type,capacity,hourly_rate) VALUES (1,'來賓汽車','CAR',10,30)"))
        connection.execute(sa.text("INSERT INTO parking_record (plate_no,area_id,entry_time) VALUES ('GUEST-1',1,'2026-11-05 09:00:00')"))
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(sa.text("INSERT INTO parking_record (plate_no,area_id,entry_time) VALUES ('GUEST-1',1,'2026-11-05 10:00:00')"))
