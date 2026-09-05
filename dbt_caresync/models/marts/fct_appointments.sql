-- Single fact table: one row per encounter (= appointment, per the
-- project's framing note). Grain: encounter_id.
select
    e.encounter_id,
    e.patient_id      as patient_key,
    e.provider_id     as provider_key,
    e.organization_id as clinic_key,
    e.payer_id        as payer_key,
    e.start_ts,
    e.stop_ts,
    e.encounter_class,
    e.encounter_code,
    e.encounter_description,
    e.base_encounter_cost,
    e.total_claim_cost,
    e.payer_coverage,
    e._run_id
from {{ ref('stg_encounters') }} e
