select
    organization_id as organization_key,
    organization_name,
    address, city, state, zip, latitude, longitude, phone, revenue, utilization
from {{ ref('stg_organizations') }}
