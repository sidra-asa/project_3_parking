-- DANGER: deletes ALL data in these project tables and the migration version.
-- Run ONLY in an authorized, dedicated, disposable project TEST database/schema.
-- Confirm current_database() and change public to your own schema if needed.
SELECT current_database() AS connected_database, current_schema() AS default_schema;

BEGIN;
DROP TABLE IF EXISTS
    public.parking_record,
    public.parking_permit,
    public.vehicle,
    public.parking_area,
    public.campus_user,
    public.login_account,
    public.alembic_version;
COMMIT;
-- Next, run: flask --app wsgi db upgrade
-- Then: flask --app wsgi create-admin
-- Then: flask --app wsgi seed-demo --yes
-- This is a destructive rebuild, NOT an upgrade migration for existing data.
