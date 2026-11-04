"""Export generated fictional data for offline review; DOES NOT connect to PostgreSQL."""
from __future__ import annotations
import argparse
import csv
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from demo_data_generator import build_demo_data, summarize_dataset  # noqa: E402

COLUMNS = {
    'campus_user': ['id', 'name', 'identity_type', 'department', 'phone'],
    'vehicle': ['id', 'plate_no', 'vehicle_type', 'user_ref'],
    'parking_area': ['id', 'area_name', 'vehicle_type', 'capacity', 'hourly_rate'],
    'parking_permit': ['id', 'vehicle_ref', 'academic_year', 'issue_date', 'valid_from',
                       'valid_to', 'permit_fee', 'payment_method', 'paid_at'],
    'parking_record': ['id', 'plate_no', 'area_ref', 'permit_ref', 'entry_time',
                       'exit_time', 'parking_fee', 'payment_method', 'paid_at'],
}


def cell(value):
    if value is None:
        return ''
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f'{value:.2f}'
    return str(value)


def main():
    parser = argparse.ArgumentParser(description='Export 30,000 synthetic parking records to CSV')
    parser.add_argument('--output', type=Path, default=ROOT / 'demo_data_30000')
    parser.add_argument('--records', type=int, default=30000)
    parser.add_argument('--active', type=int, default=450)
    parser.add_argument('--seed', type=int, default=20261103)
    parser.add_argument('--as-of', default='2026-11-03T18:00:00+08:00')
    args = parser.parse_args()
    as_of = datetime.fromisoformat(args.as_of)
    dataset = build_demo_data(count=args.records, active_count=args.active,
                              seed=args.seed, as_of=as_of)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, columns in COLUMNS.items():
        with (args.output / f'{name}.csv').open('w', encoding='utf-8-sig', newline='') as fp:
            writer = csv.writer(fp)
            writer.writerow(columns)
            for record in dataset[name]:
                writer.writerow([cell(record.get(k)) for k in columns])
    summary = summarize_dataset(dataset)
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
