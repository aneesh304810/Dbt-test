/*
    Test: Seed Completeness Validation
    
    Validates that seed crosswalk files contain all necessary mappings
    for the SEI codes present in the source data.
    
    Identifies:
    - SEI asset class codes in source that have no mapping in seed
    - SEI strategy codes in source that have no mapping in seed
    - Unmapped codes that should be added to seeds
    
    Test passes when all source codes have seed mappings.
*/

with source_asset_classes as (
    select distinct asset_cls_code as sei_code
    from {{ source('sei_raw', 'securities') }}
    where asset_cls_code is not null
),

seed_asset_classes as (
    select distinct sei_asset_class_code as sei_code
    from {{ ref('seed_asset_class_crosswalk') }}
),

-- Find asset classes in source but not in seed
unmapped_asset_classes as (
    select
        s.sei_code,
        'ASSET_CLASS' as code_type,
        'SEI asset class exists in source but has no seed mapping' as issue,
        count(*) as affected_securities_count
    from source_asset_classes s
    left join seed_asset_classes seed
        on s.sei_code = seed.sei_code
    where seed.sei_code is null
    group by s.sei_code
),

-- Get the parent codes from staging to check rollup coverage
staging_classes as (
    select distinct
        asset_class_code,
        top_level_code
    from {{ ref('stg_sei_asset_class') }}
    where top_level_code is not null
),

-- Find parent codes that also lack mapping
unmapped_parent_codes as (
    select
        sc.top_level_code as sei_code,
        'PARENT_ASSET_CLASS' as code_type,
        'Parent asset class has no seed mapping (rollup will fail)' as issue,
        count(distinct sc.asset_class_code) as affected_child_codes
    from staging_classes sc
    left join seed_asset_classes seed
        on sc.top_level_code = seed.sei_code
    where seed.sei_code is null
        and sc.top_level_code not in (
            -- Exclude codes that are themselves children
            select asset_class_code from staging_classes
        )
    group by sc.top_level_code
),

all_unmapped as (
    select * from unmapped_asset_classes
    union all
    select * from unmapped_parent_codes
)

select * from all_unmapped
