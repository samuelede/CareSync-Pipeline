-- PHI already stripped at the staging boundary (stg_patients.sql), this
-- model just renames the surrogate key, it does not re-select from RAW.
select
    patient_id as patient_key,
    birthdate, deathdate, marital_status, race, ethnicity, gender,
    city, state, county, fips, zip, healthcare_expenses, healthcare_coverage
from {{ ref('stg_patients') }}
