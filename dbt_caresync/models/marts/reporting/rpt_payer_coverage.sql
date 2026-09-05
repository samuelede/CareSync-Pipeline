-- Q3: payer coverage mix, how much of total claim cost each payer covers.
select
    pay.payer_key,
    pay.payer_name,
    pay.ownership,
    count(*)                                   as appointment_count,
    sum(f.total_claim_cost)                    as total_claim_cost,
    sum(f.payer_coverage)                      as total_payer_coverage,
    div0(sum(f.payer_coverage), sum(f.total_claim_cost)) as coverage_ratio
from {{ ref('fct_appointments') }} f
join {{ ref('dim_payers') }} pay on f.payer_key = pay.payer_key
group by 1, 2, 3
