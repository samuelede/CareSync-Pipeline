select
    "Id"                    as payer_id,
    "NAME"                  as payer_name,
    "OWNERSHIP"             as ownership,
    "STATE_HEADQUARTERED"   as state_headquartered,
    "AMOUNT_COVERED"        as amount_covered,
    "AMOUNT_UNCOVERED"      as amount_uncovered,
    "COVERED_ENCOUNTERS"    as covered_encounters,
    "UNCOVERED_ENCOUNTERS"  as uncovered_encounters,
    "UNIQUE_CUSTOMERS"      as unique_customers,
    _run_id,
    _loaded_at
from {{ source('raw', 'payers') }}
qualify row_number() over (partition by "Id" order by _loaded_at desc) = 1
