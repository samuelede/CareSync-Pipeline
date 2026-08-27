select
    "START"        as start_ts,
    "STOP"          as stop_ts,
    "PATIENT"        as patient_id,
    "ENCOUNTER"       as encounter_id,
    "SYSTEM"           as code_system,
    "CODE"              as condition_code,
    "DESCRIPTION"        as condition_description,
    _run_id,
    _loaded_at
from {{ source('raw', 'conditions') }}
