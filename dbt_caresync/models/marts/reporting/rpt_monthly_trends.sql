-- Monthly appointment volume and cost trend, across all clinics.
select
    date_trunc('month', try_to_timestamp_ntz(start_ts::varchar))   as appointment_month,
    encounter_class,
    count(*)                        as appointment_count,
    sum(total_claim_cost)           as total_claim_cost,
    avg(total_claim_cost)           as avg_claim_cost
from {{ ref('fct_appointments') }}
group by 1, 2
