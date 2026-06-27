-- Enable PostGIS and supporting extensions on first DB initialization (SRS §20).
-- The postgis/postgis image runs this once when the data volume is empty.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
