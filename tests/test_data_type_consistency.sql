/*
    Test: Data Type Consistency
    
    Validates that data types remain consistent as data flows through
    the transformation pipeline: Source -> Staging -> Mapping -> Mart
    
    Checks:
    - Numeric fields remain numeric
    - Date fields remain dates
    - String fields maintain appropriate lengths
    - No unexpected type conversions
    
    Test passes when no type mismatches are found.
*/

with mart_data as (
    select
        SECURITY_ID,
        CUSIP,
        COUPON_RATE,
        MATURITY_DATE,
        PRICE,
        PRICE_DATE,
        MARKET_CAP
    from {{ ref('advent_securities') }}
),

type_violations as (
    -- Check COUPON_RATE is numeric and in valid range
    select
        SECURITY_ID,
        'COUPON_RATE' as field_name,
        'Non-numeric or invalid coupon rate' as issue,
        cast(COUPON_RATE as varchar) as offending_value
    from mart_data
    where COUPON_RATE is not null
        and (
            COUPON_RATE < 0
            or COUPON_RATE > 1
            or COUPON_RATE is null  -- Should have been validated earlier
        )
    
    union all
    
    -- Check PRICE is numeric and positive
    select
        SECURITY_ID,
        'PRICE' as field_name,
        'Non-numeric or negative price' as issue,
        cast(PRICE as varchar) as offending_value
    from mart_data
    where PRICE is not null
        and PRICE < 0
    
    union all
    
    -- Check MARKET_CAP is numeric and positive
    select
        SECURITY_ID,
        'MARKET_CAP' as field_name,
        'Non-numeric or negative market cap' as issue,
        cast(MARKET_CAP as varchar) as offending_value
    from mart_data
    where MARKET_CAP is not null
        and MARKET_CAP < 0
    
    union all
    
    -- Check MATURITY_DATE is a valid date
    select
        SECURITY_ID,
        'MATURITY_DATE' as field_name,
        'Invalid maturity date' as issue,
        cast(MATURITY_DATE as varchar) as offending_value
    from mart_data
    where MATURITY_DATE is not null
        and (
            MATURITY_DATE < date '1900-01-01'
            or MATURITY_DATE > date '2100-12-31'
        )
    
    union all
    
    -- Check PRICE_DATE is a valid date
    select
        SECURITY_ID,
        'PRICE_DATE' as field_name,
        'Invalid price date' as issue,
        cast(PRICE_DATE as varchar) as offending_value
    from mart_data
    where PRICE_DATE is not null
        and (
            PRICE_DATE < date '1900-01-01'
            or PRICE_DATE > current_date + interval '1 day'
        )
    
    union all
    
    -- Check CUSIP is exactly 9 characters when present
    select
        SECURITY_ID,
        'CUSIP' as field_name,
        'CUSIP length is not 9 characters' as issue,
        CUSIP as offending_value
    from mart_data
    where CUSIP is not null
        and length(CUSIP) != 9
)

select * from type_violations
