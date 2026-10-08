-- locations: 4 rows
-- Exported from Supabase for deterministic seeding
-- Operators get identical data regardless of when they run the seed script

-- Clear existing data
TRUNCATE TABLE locations CASCADE;

INSERT INTO locations (location_id, name, type, address, tz, lat, lng, active, created_at, updated_at) VALUES ('35a626a3-4162-4b47-afdd-9c99d4766387', 'Auckland Hospital Outpatient Clinic', 'OPD', '2 Park Road, Grafton, Auckland 1023, New Zealand', 'Pacific/Auckland', NULL, NULL, 1, 1771371926, 1771371926);
INSERT INTO locations (location_id, name, type, address, tz, lat, lng, active, created_at, updated_at) VALUES ('3e30e01c-fc76-4366-afe3-b4c66c1661a7', 'Auckland Hospital Cardiology Clinic', 'CLINIC', '2 Park Road, Grafton, Auckland 1023, New Zealand', 'Pacific/Auckland', NULL, NULL, 1, 1771371926, 1771371926);
INSERT INTO locations (location_id, name, type, address, tz, lat, lng, active, created_at, updated_at) VALUES ('65e6b552-1098-40f0-b433-c07809d75ec7', 'Auckland Hospital', 'HOSPITAL', '2 Park Road, Grafton, Auckland 1023, New Zealand', 'Pacific/Auckland', NULL, NULL, 1, 1771371926, 1771371926);
INSERT INTO locations (location_id, name, type, address, tz, lat, lng, active, created_at, updated_at) VALUES ('8bdfd35d-5dee-417a-b024-a581e8518349', 'Auckland Hospital Laboratory', 'LAB', '2 Park Road, Grafton, Auckland 1023, New Zealand', 'Pacific/Auckland', NULL, NULL, 1, 1771371926, 1771371926);

-- End of locations
