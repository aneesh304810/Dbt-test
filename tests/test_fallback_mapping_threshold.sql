/*
    Test: Fallback Mapping Threshold
    
    Ensures that the percentage of securities using FALLBACK mapping
    methods stays below acceptable thresholds.
    
    Thresholds:
    - L1 (Asset Class) FALLBACK: < 10% (warning) or < 20% (error)
    - L2 (Strategy) FALLBACK: < 15% (warning) or < 25% (error)
    
    High fallback rates indicate:
    - Incomplete seed crosswalks
    - New SEI codes not yet mapped
    - Data quality issues in source
    
    Test passes when fallback percentages are below thresholds.
*/

with mart_data as (
    select
        SECURITY_ID,
        _L1_MAPPING_METHOD,
        _L2_MAPPING_METHOD
    from {{ ref('advent_securities') }}
),

metrics as (
    select
        count(*) as total_securities,
        
        -- L1 Fallback Metrics
        sum(case when _L1_MAPPING_METHOD = 'FALLBACK' then 1 else 0 end) as l1_fallback_count,
        round(
            sum(case when _L1_MAPPING_METHOD = 'FALLBACK' then 1 else 0 end) * 100.0 / count(*),
            2
        ) as l1_fallback_pct,
        
        -- L2 Fallback Metrics
        sum(case when _L2_MAPPING_METHOD = 'FALLBACK' then 1 else 0 end) as l2_fallback_count,
        round(
            sum(case when _L2_MAPPING_METHOD = 'FALLBACK' then 1 else 0 end) * 100.0 / count(*),
            2
        ) as l2_fallback_pct
    from mart_data
),

threshold_violations as (
    select
        'L1_FALLBACK_RATE_EXCEEDED' as violation_type,
        l1_fallback_pct as observed_pct,
        20.0 as threshold_pct,
        l1_fallback_count as affected_securities,
        total_securities
    from metrics
    where l1_fallback_pct > 20.0
    
    union all
    
    select
        'L2_FALLBACK_RATE_EXCEEDED' as violation_type,
        l2_fallback_pct as observed_pct,
        25.0 as threshold_pct,
        l2_fallback_count as affected_securities,
        total_securities
    from metrics
    where l2_fallback_pct > 25.0
)

select * from threshold_violations
