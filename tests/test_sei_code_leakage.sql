/*
    Test: SEI Code Leakage Detection
    
    Ensures that no SEI-specific codes or naming conventions have
    leaked into the final Advent output fields.
    
    Checks for common SEI patterns:
    - Underscore naming (EQ_DOM, FI_CORP, ALT_HF)
    - "sei_" prefix
    - Known SEI codes in business columns
    
    Test passes when no rows are returned (count = 0).
*/

with mart_data as (
    select
        SECURITY_ID,
        ASSET_CLASS,
        ASSET_CLASS_CODE,
        STRATEGY_CODE,
        STRATEGY_DESCRIPTION,
        SECURITY_NAME,
        SECURITY_DESCRIPTION
    from {{ ref('advent_securities') }}
),

leakage_patterns as (
    select
        SECURITY_ID,
        'ASSET_CLASS contains underscore pattern' as leakage_type,
        ASSET_CLASS as offending_value
    from mart_data
    where ASSET_CLASS like '%\_%'  -- Contains underscore
       or ASSET_CLASS like '%EQ_DOM%'
       or ASSET_CLASS like '%FI_GOV%'
       or ASSET_CLASS like '%ALT_%'
    
    union all
    
    select
        SECURITY_ID,
        'STRATEGY_DESCRIPTION contains SEI pattern' as leakage_type,
        STRATEGY_DESCRIPTION as offending_value
    from mart_data
    where STRATEGY_DESCRIPTION like '%sei%'
       or STRATEGY_DESCRIPTION like '%SEI%'
    
    union all
    
    select
        SECURITY_ID,
        'SECURITY_NAME contains SEI reference' as leakage_type,
        SECURITY_NAME as offending_value
    from mart_data
    where SECURITY_NAME like '%sei_%'
       or SECURITY_NAME like '%SEI_%'
    
    union all
    
    select
        SECURITY_ID,
        'ASSET_CLASS_CODE has invalid format' as leakage_type,
        ASSET_CLASS_CODE as offending_value
    from mart_data
    where ASSET_CLASS_CODE like '%\_%'  -- Advent codes should not have underscores
)

select * from leakage_patterns
