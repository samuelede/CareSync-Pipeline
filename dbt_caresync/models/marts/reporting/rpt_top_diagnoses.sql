-- Most common condition codes across the reporting window.
select
    condition_code,
    condition_description,
    count(*)                        as diagnosis_count,
    count(distinct patient_key)     as distinct_patients
from {{ ref('conditions_detail') }}
group by 1, 2
order by diagnosis_count desc
