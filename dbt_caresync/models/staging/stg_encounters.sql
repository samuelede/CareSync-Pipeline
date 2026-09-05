select
    "Id"                                          as encounter_id,
    try_to_timestamp_ntz("START")                 as start_ts,
    try_to_timestamp_ntz("STOP")                  as stop_ts,
    "PATIENT"                                     as patient_id,
    "ORGANIZATION"                                as organization_id,
    "PROVIDER"                                    as provider_id,
    "PAYER"                                       as payer_id,
    lower(nullif(trim("ENCOUNTERCLASS"), ''))      as encounter_class,
    nullif(trim("CODE"), '')                      as encounter_code,
    nullif(trim("DESCRIPTION"), '')               as encounter_description,
    try_to_number("BASE_ENCOUNTER_COST", 18, 2)   as base_encounter_cost,
    try_to_number("TOTAL_CLAIM_COST", 18, 2)      as total_claim_cost,
    try_to_number("PAYER_COVERAGE", 18, 2)        as payer_coverage,
    _run_id,
    _loaded_at
from {{ source('raw', 'encounters') }}
