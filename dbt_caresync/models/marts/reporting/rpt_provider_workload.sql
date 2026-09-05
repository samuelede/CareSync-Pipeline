-- Q2: provider workload, appointment count and average cost per provider.
select
    p.provider_key,
    p.provider_name,
    p.speciality,
    count(*)                            as appointment_count,
    avg(f.total_claim_cost)             as avg_claim_cost,
    min(f.start_ts)                     as first_appointment,
    max(f.start_ts)                     as last_appointment
from {{ ref('fct_appointments') }} f
join {{ ref('dim_providers') }} p on f.provider_key = p.provider_key
group by 1, 2, 3
