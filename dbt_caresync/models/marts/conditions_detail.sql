-- One row per condition, FK back to fct_appointments via encounter_id.
select
    c.encounter_id,
    c.patient_key,
    c.start_ts,
    c.stop_ts,
    c.code_system,
    c.condition_code,
    c.condition_description,
    c._run_id
from (
    select
        encounter_id, patient_id as patient_key, start_ts, stop_ts,
        code_system, condition_code, condition_description, _run_id
    from {{ ref('stg_conditions') }}
) c
