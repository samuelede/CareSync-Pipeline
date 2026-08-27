select
    provider_id as provider_key,
    organization_id as clinic_key,
    provider_name, gender, speciality, city, state, zip, utilization
from {{ ref('stg_providers') }}
