select
    try_to_timestamp_ntz("START")                 as start_ts,
    try_to_timestamp_ntz("STOP")                  as stop_ts,
    "PATIENT"                                     as patient_id,
    "ENCOUNTER"                                   as encounter_id,
    nullif(trim("SYSTEM"), '')                    as code_system,
    nullif(trim("CODE"), '')                      as condition_code,
    nullif(trim("DESCRIPTION"), '')               as condition_description,
    _run_id,
    _loaded_at
from {{ source('raw', 'conditions') }}
