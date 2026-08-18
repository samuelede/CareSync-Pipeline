-- One row per condition, FK back to fct_appointments via encounter_id.
select
    c.encounter_id,
    c.patient_id as patient_key,
    c.start_ts,
    c.stop_ts,
    c.condition_code,
    c.condition_description,
    c._run_id
from {{ ref('stg_conditions') }} c
