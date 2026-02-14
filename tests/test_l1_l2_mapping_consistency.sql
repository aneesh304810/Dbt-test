/*
    Test: L1/L2 Mapping Consistency
    
    Validates that every strategy code (L2) in the mart is aligned with
    the correct asset class (L1) according to the seed crosswalk.
    
    This catches misconfigured mappings where a strategy is assigned
    to a security with an incompatible asset class.
    
    Test passes when no rows are returned (count = 0).
*/

with mart_data as (
    select
        SECURITY_ID,
        ASSET_CLASS_CODE,
        STRATEGY_CODE,
        STRATEGY_DESCRIPTION
    from {{ ref('advent_securities') }}
),

strategy_seed as (
    select
        advent_strategy_code,
        advent_asset_class_code,
        advent_strategy_desc
    from {{ ref('seed_strategy_crosswalk') }}
),

mismatches as (
    select
        m.SECURITY_ID,
        m.ASSET_CLASS_CODE as mart_asset_class,
        m.STRATEGY_CODE,
        s.advent_asset_class_code as expected_asset_class
    from mart_data m
    inner join strategy_seed s
        on m.STRATEGY_CODE = s.advent_strategy_code
    where m.ASSET_CLASS_CODE != s.advent_asset_class_code
)

select * from mismatches
