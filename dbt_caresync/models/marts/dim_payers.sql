select
    payer_id as payer_key,
    payer_name, ownership, state_headquartered, amount_covered,
    amount_uncovered, covered_encounters, uncovered_encounters,
    unique_customers
from {{ ref('stg_payers') }}
