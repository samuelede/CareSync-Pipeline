select
    "Id"                    as encounter_id,
    "START"                  as start_ts,
    "STOP"                    as stop_ts,
    "PATIENT"                  as patient_id,
    "ORGANIZATION"               as organization_id,
    "PROVIDER"                    as provider_id,
    "PAYER"                        as payer_id,
    "ENCOUNTERCLASS"                as encounter_class,
    "CODE"                            as encounter_code,
    "DESCRIPTION"                      as encounter_description,
    "BASE_ENCOUNTER_COST"               as base_encounter_cost,
    "TOTAL_CLAIM_COST"                   as total_claim_cost,
    "PAYER_COVERAGE"                      as payer_coverage,
    _run_id,
    _loaded_at
from {{ source('raw', 'encounters') }}
