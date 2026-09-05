select
    provider_id as provider_key,
    organization_id as clinic_key,
    provider_name, gender, speciality, city, state, zip,
    lifetime_encounters, lifetime_procedures, npi
from {{ ref('stg_providers') }}
