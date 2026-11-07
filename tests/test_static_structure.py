"""Dependency-free checks that can run even without downloading Flask packages."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_project_contains_six_models():
    tree = ast.parse((ROOT / 'app/models/__init__.py').read_text())
    classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert {'CampusUser','Vehicle','ParkingPermit','ParkingArea','ParkingRecord'} <= classes
    accounts = ast.parse((ROOT / 'app/models/login_account.py').read_text())
    assert any(n.name == 'LoginAccount' for n in ast.walk(accounts) if isinstance(n,ast.ClassDef))


def test_config_no_hardcoded_school_credentials():
    config = (ROOT/'config.py').read_text()
    assert "os.getenv('DATABASE_URL'" in config
    assert 'school_password' not in config


def test_migration_and_deployment_files_exist():
    for path in ['migrations/env.py','migrations/versions/0001_initial_schema.py',
                 'render.yaml','Dockerfile','README.md','sql/schema.sql']:
        assert (ROOT/path).exists(),path


def test_record_model_is_independent_of_vehicle_row():
    source = (ROOT / 'app/models/__init__.py').read_text()
    records = source.split('class ParkingRecord(db.Model):', 1)[1]
    assert "plate_no = db.Column(db.String(20)" in records
    assert "db.ForeignKey('vehicle.vehicle_id')" not in records
    assert "'uq_one_open_record_per_plate'" in records
    seed = (ROOT / 'app/services/seed.py').read_text()
    assert "plate_no=row['plate_no']" in seed
