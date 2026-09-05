-- Q1: weekly appointment volume by clinic.
select
    c.clinic_key,
    c.clinic_name,
    date_trunc('week', try_to_timestamp_ntz(f.start_ts::varchar))  as appointment_week,
    count(*)                        as appointment_count,
    sum(f.total_claim_cost)         as total_claim_cost
from {{ ref('fct_appointments') }} f
join {{ ref('dim_clinics') }} c on f.clinic_key = c.clinic_key
group by 1, 2, 3
