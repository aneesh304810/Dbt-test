/*
    Test: Orphaned Securities Detection
    
    Identifies securities that exist in the source but are missing
    from the mart (data loss), or exist in the mart but not in the
    source (phantom records).
    
    Test passes when no rows are returned (count = 0).
*/

with source_securities as (
    select cast(sec_id as varchar(50)) as security_id
    from {{ source('sei_raw', 'securities') }}
),

mart_securities as (
    select SECURITY_ID as security_id
    from {{ ref('advent_securities') }}
),

-- Securities in source but missing from mart (DATA LOSS)
missing_from_mart as (
    select
        s.security_id,
        'SOURCE_TO_MART' as orphan_type,
        'Security exists in SEI source but missing from Advent mart' as issue_description
    from source_securities s
    left join mart_securities m
        on s.security_id = m.security_id
    where m.security_id is null
),

-- Securities in mart but missing from source (PHANTOM DATA)
phantom_in_mart as (
    select
        m.security_id,
        'MART_TO_SOURCE' as orphan_type,
        'Security exists in Advent mart but missing from SEI source' as issue_description
    from mart_securities m
    left join source_securities s
        on m.security_id = s.security_id
    where s.security_id is null
),

all_orphans as (
    select * from missing_from_mart
    union all
    select * from phantom_in_mart
)

select * from all_orphans
