-- Clinic dimension (Synthea calls these "organizations", the physical
-- clinics in Nexora's network). Grain: one row per clinic.
select
    organization_id as clinic_key,
    organization_name as clinic_name,
    address, city, state, zip, latitude, longitude, phone, revenue,
    utilization, npi
from {{ ref('stg_organizations') }}
