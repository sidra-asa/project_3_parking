"""Opt-in fictional parking data import; never writes without --yes."""
from datetime import datetime

import click

from app.extensions import db
from app.models import CampusUser, ParkingArea, ParkingPermit, ParkingRecord, Vehicle
from demo_data_generator import build_demo_data, summarize_dataset, DEFAULT_AS_OF


def register_seed_command(app):
    @app.cli.command('seed-demo')
    @click.option('--yes', 'confirmed', is_flag=True,
                  help='確認寫入目前 DATABASE_URL 指向的空白測試資料庫')
    @click.option('--records', default=30000, show_default=True, type=click.IntRange(min=1),
                  help='停車進場紀錄總筆數（未離場紀錄由快照自然產生）')
    @click.option('--seed', default=20261103, show_default=True, type=int,
                  help='固定亂數種子')
    @click.option('--as-of', default=DEFAULT_AS_OF.isoformat(), show_default=True,
                  help='模擬快照（須在 2026-06-28，ISO 8601，附時區）')
    def seed_demo(confirmed, records, seed, as_of):
        if not confirmed:
            raise click.ClickException('為避免誤寫入學校資料庫，必須加入 --yes')
        if any(db.session.query(cls).first() is not None
               for cls in (CampusUser, Vehicle, ParkingArea, ParkingPermit, ParkingRecord)):
            raise click.ClickException('業務資料表已有紀錄，為避免污染現有資料，取消匯入')
        try:
            reference = datetime.fromisoformat(as_of)
            if reference.tzinfo is None:
                raise ValueError('timestamp without timezone')
        except ValueError as exc:
            raise click.ClickException('--as-of 必須是附時區的 ISO 8601 時間') from exc
        try:
            rows = build_demo_data(count=records, seed=seed, as_of=reference)
        except (ValueError, RuntimeError) as exc:
            raise click.ClickException(str(exc)) from exc
        try:
            user_map = {}
            for row in rows['campus_user']:
                user = CampusUser(name=row['name'], identity_type=row['identity_type'],
                                  department=row['department'], phone=row['phone'])
                db.session.add(user)
                user_map[row['id']] = user
            db.session.flush()
            area_map = {}
            for row in rows['parking_area']:
                area = ParkingArea(area_name=row['area_name'], vehicle_type=row['vehicle_type'],
                                   capacity=row['capacity'], hourly_rate=row['hourly_rate'])
                db.session.add(area)
                area_map[row['id']] = area
            db.session.flush()
            vehicle_map = {}
            for row in rows['vehicle']:
                v = Vehicle(plate_no=row['plate_no'], vehicle_type=row['vehicle_type'],
                            user_id=user_map[row['user_ref']].user_id if row['user_ref'] else None)
                db.session.add(v)
                vehicle_map[row['id']] = v
            db.session.flush()
            permit_map = {}
            for row in rows['parking_permit']:
                p = ParkingPermit(vehicle_id=vehicle_map[row['vehicle_ref']].vehicle_id,
                                  academic_year=row['academic_year'], issue_date=row['issue_date'],
                                  valid_from=row['valid_from'], valid_to=row['valid_to'],
                                  permit_fee=row['permit_fee'], payment_method=row['payment_method'],
                                  paid_at=row['paid_at'])
                db.session.add(p)
                permit_map[row['id']] = p
            db.session.flush()
            batch = []
            for row in rows['parking_record']:
                record = ParkingRecord(
                    plate_no=row['plate_no'], area_id=area_map[row['area_ref']].area_id,
                    permit_id=permit_map[row['permit_ref']].permit_id if row['permit_ref'] else None,
                    entry_time=row['entry_time'], exit_time=row['exit_time'],
                    parking_fee=row['parking_fee'], payment_method=row['payment_method'],
                    paid_at=row['paid_at'])
                batch.append(record)
                if len(batch) >= 1000:
                    db.session.add_all(batch)
                    db.session.flush()
                    batch.clear()
            if batch:
                db.session.add_all(batch)
                db.session.flush()
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        summary = summarize_dataset(rows, as_of=reference)
        click.echo(f"示範資料完成：{summary['campus_users']} 人、{summary['vehicles']} 車、"
                   f"{summary['areas']} 區、{summary['permits']} 張停車證、"
                   f"{summary['records']} 筆停車紀錄（截至 {summary['as_of']} 尚有 "
                   f"{summary['active_records']} 筆未離場）")
