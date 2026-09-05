select
    "Id"                                          as payer_id,
    nullif(trim("NAME"), '')                      as payer_name,
    upper(nullif(trim("OWNERSHIP"), ''))           as ownership,
    nullif(trim("STATE_HEADQUARTERED"), '')       as state_headquartered,
    try_to_number("AMOUNT_COVERED", 18, 2)        as amount_covered,
    try_to_number("AMOUNT_UNCOVERED", 18, 2)      as amount_uncovered,
    try_to_number("COVERED_ENCOUNTERS")           as covered_encounters,
    try_to_number("UNCOVERED_ENCOUNTERS")         as uncovered_encounters,
    try_to_number("UNIQUE_CUSTOMERS")             as unique_customers,
    _run_id,
    _loaded_at
from {{ source('raw', 'payers') }}
qualify row_number() over (partition by "Id" order by _loaded_at desc) = 1
