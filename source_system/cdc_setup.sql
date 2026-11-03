-- Run AFTER loading data, as a superuser (Cloud SQL: cloudsqlsuperuser).
-- Usage: psql -v ds_password="'change-me'" -f source_system/cdc_setup.sql
-- Prereq: wal_level=logical (docker-compose does this; on Cloud SQL set flag cloudsql.logical_decoding=on).
CREATE ROLE datastream_user WITH REPLICATION LOGIN PASSWORD :ds_password;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO datastream_user;
GRANT USAGE ON SCHEMA public TO datastream_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO datastream_user;
CREATE PUBLICATION datastream_pub FOR ALL TABLES;
SELECT PG_CREATE_LOGICAL_REPLICATION_SLOT('datastream_slot', 'pgoutput');
