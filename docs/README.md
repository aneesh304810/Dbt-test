# SEI to Advent Test Automation Suite

## 📋 Overview

This comprehensive test automation suite provides **multi-layered data quality validation** for the SEI to Advent Advantage transformation pipeline. It ensures data accuracy, completeness, and consistency across all transformation stages.

## 🏗️ Architecture

### Test Layers

```
┌─────────────────────────────────────────────────────┐
│         Layer 1: dbt Native Tests                    │
│  • Schema validation                                 │
│  • Referential integrity                             │
│  • Data type checks                                  │
│  • Business rule validation                          │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│         Layer 2: Custom SQL Tests                    │
│  • L1/L2 mapping consistency                         │
│  • SEI code leakage detection                        │
│  • Orphaned records detection                        │
│  • Fallback threshold monitoring                     │
│  • Seed completeness validation                      │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│         Layer 3: DuckDB Validations                  │
│  • Row count reconciliation                          │
│  • Data quality metrics                              │
│  • Format validation                                 │
│  • Coverage analysis                                 │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│    Layer 4: Great Expectations (Optional)            │
│  • Advanced statistical validation                   │
│  • Distribution analysis                             │
│  • Anomaly detection                                 │
└─────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

```bash
# Install Python dependencies
pip install dbt-core dbt-duckdb duckdb pandas great-expectations

# Install dbt packages
dbt deps
```

### Running Tests

#### Option 1: Run All Tests (Recommended)

```bash
python python_tests/comprehensive_test_suite.py
```

#### Option 2: Run Only dbt Tests

```bash
dbt test
```

#### Option 3: Run Specific Test Categories

```bash
# Run only critical tests
python python_tests/comprehensive_test_suite.py --selector "tag:critical"

# Skip Great Expectations
python python_tests/comprehensive_test_suite.py --skip-gx

# Skip DuckDB validations
python python_tests/comprehensive_test_suite.py --skip-duckdb
```

## 📊 Test Coverage

### dbt Native Tests (150+ tests)

#### Sources Layer
- ✅ Primary key uniqueness
- ✅ Not null constraints
- ✅ Referential integrity
- ✅ Data format validation (CUSIP, ISIN, SEDOL)
- ✅ Currency and country code format
- ✅ Date range validation
- ✅ Freshness checks

#### Staging Layer
- ✅ Schema validation
- ✅ Uniqueness constraints
- ✅ Completeness checks

#### Mapping Layer
- ✅ Mapping method validation
- ✅ Crosswalk integrity
- ✅ Parent-child relationships

#### Mart Layer
- ✅ All identifier formats (CUSIP, ISIN, SEDOL, Ticker)
- ✅ Asset class code validation
- ✅ Strategy code validation
- ✅ Security type validation
- ✅ Status validation
- ✅ Currency/country code format
- ✅ Date range validation
- ✅ Price and market cap ranges
- ✅ Mapping method validation
- ✅ Audit column validation

### Custom SQL Tests (6 tests)

1. **L1/L2 Mapping Consistency**
   - Validates that strategy codes align with correct asset classes
   - Detects misconfigured mappings
   
2. **SEI Code Leakage Detection**
   - Ensures no SEI-specific naming conventions in Advent output
   - Checks for underscore patterns, SEI prefixes
   
3. **Orphaned Securities Detection**
   - Identifies data loss (source → mart)
   - Identifies phantom records (mart → source)
   
4. **Fallback Mapping Threshold**
   - L1 FALLBACK < 20%
   - L2 FALLBACK < 25%
   - Monitors mapping quality
   
5. **Seed Completeness Validation**
   - Verifies all source codes have seed mappings
   - Checks parent code coverage
   
6. **Data Type Consistency**
   - Validates numeric ranges
   - Validates date formats
   - Validates string lengths

### DuckDB Validations (25+ checks)

#### Schema Validation
- Column existence
- Data types

#### Reconciliation
- Row count matching across layers
- No duplicate primary keys

#### Completeness
- No null values in critical fields
- Required field population

#### Format Validation
- CUSIP (9 chars)
- Currency (3 chars, ISO 4217)
- Country (2 chars, ISO 3166-1)

#### Data Leakage Prevention
- No SEI code patterns in business columns
- No underscore naming in Advent fields

#### Quality Metrics
- FALLBACK rate thresholds
- DIRECT mapping percentages
- Coverage metrics

#### Referential Integrity
- Asset class code existence in seeds
- Strategy code existence in seeds
- L1/L2 consistency

#### Business Rules
- Active securities have valid prices
- Fixed income securities have maturity dates

### Great Expectations (Optional)

- Statistical validation
- Distribution analysis
- Anomaly detection
- Historical comparisons

## 📈 Reports

### HTML Report

Generated at: `reports/comprehensive_test_report_latest.html`

Features:
- ✅ Overall pass/fail status
- 📊 Visual metrics and progress bars
- 📋 Detailed test results by phase
- 🎨 Color-coded severity indicators
- 🔍 Drill-down capability

### JSON Report

Generated at: `reports/test_report_latest.json`

Features:
- Machine-readable format
- CI/CD integration support
- Historical trend analysis
- Programmatic access

## 🔧 Configuration

### Update dbt Packages

Edit `packages.yml`:

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.1.1
  - package: calogica/dbt_expectations
    version: 0.10.1
  - package: dbt-labs/dbt_project_evaluator
    version: 0.8.0
  - package: dbt-labs/audit_helper
    version: 0.9.0
  - package: dbt-labs/codegen
    version: 0.12.1
```

Then run:

```bash
dbt deps
```

### Configure Test Thresholds

Edit threshold values in:
- `tests/test_fallback_mapping_threshold.sql`
- `python_tests/comprehensive_test_suite.py` (DuckDB checks)

### Add Custom Tests

1. **dbt Tests**: Add to `schemas/*.yml`
2. **Custom SQL**: Add to `tests/*.sql`
3. **Python Validations**: Add to `define_duckdb_checks()` in test suite

## 🔄 CI/CD Integration

### GitHub Actions

The included workflow (`.github/workflows/test_automation.yml`) runs:

1. **On Push/PR**: Full test suite
2. **Scheduled**: Daily at 6 AM UTC
3. **Quality Gates**: Enforce minimum pass rates
4. **Artifacts**: Upload reports and dbt artifacts
5. **PR Comments**: Automatic test result summaries

### Configuration

Copy the workflow file:

```bash
cp ci_cd/github_actions.yml .github/workflows/test_automation.yml
```

### Quality Gates

Current thresholds:
- **Minimum Pass Rate**: 95%
- **Maximum L1 Fallback**: 20%
- **Maximum L2 Fallback**: 25%

Adjust in `.github/workflows/test_automation.yml`

## 📁 File Structure

```
dbt_sei_to_advent/
├── models/
│   ├── sources/
│   │   └── sei_sources.yml (enhanced with tests)
│   ├── staging/
│   │   └── stg_staging.yml
│   ├── mappings/
│   │   └── map_mappings.yml
│   └── marts/
│       └── mart_advent.yml (enhanced with 50+ tests)
├── tests/
│   ├── test_l1_l2_mapping_consistency.sql
│   ├── test_sei_code_leakage.sql
│   ├── test_orphaned_securities.sql
│   ├── test_fallback_mapping_threshold.sql
│   ├── test_seed_completeness.sql
│   └── test_data_type_consistency.sql
├── python_tests/
│   └── comprehensive_test_suite.py
├── ci_cd/
│   └── github_actions.yml
├── reports/ (generated)
│   ├── comprehensive_test_report_latest.html
│   └── test_report_latest.json
├── packages.yml (enhanced)
└── README.md (this file)
```

## 🎯 Best Practices

### 1. Run Tests Locally Before Committing

```bash
# Full test suite
python python_tests/comprehensive_test_suite.py

# Check for critical failures
dbt test --select "tag:critical"
```

### 2. Review Test Reports

Always review HTML reports for:
- Failed tests requiring investigation
- High fallback rates
- Data quality trends

### 3. Update Seeds When Needed

If you see "Seed Completeness" failures:

```bash
# Add new mappings to:
# - seeds/seed_asset_class_crosswalk.csv
# - seeds/seed_strategy_crosswalk.csv

# Then reload seeds
dbt seed
```

### 4. Monitor Fallback Rates

Track fallback mapping trends:
- Increasing rates indicate incomplete mappings
- Review new SEI codes
- Update seed crosswalks

### 5. Investigate Leakage Failures

If "SEI Code Leakage" tests fail:
- Check transformation logic
- Verify seed data
- Review join conditions

## 🐛 Troubleshooting

### Issue: Tests fail with "relation does not exist"

**Solution**: Run models first
```bash
dbt run
dbt test
```

### Issue: DuckDB connection errors

**Solution**: Check database path
```bash
export DUCKDB_PATH="./dbt_sei_to_advent.duckdb"
```

### Issue: Great Expectations not found

**Solution**: Install dependencies
```bash
pip install great-expectations
```

### Issue: High test execution time

**Solution**: Run selective tests
```bash
# Run only critical tests
dbt test --select "tag:critical"

# Skip expensive tests
python python_tests/comprehensive_test_suite.py --skip-gx
```

## 📚 Additional Resources

### dbt Documentation
- [dbt Testing Guide](https://docs.getdbt.com/docs/building-a-dbt-project/tests)
- [dbt_utils Package](https://hub.getdbt.com/dbt-labs/dbt_utils/latest/)
- [dbt_expectations Package](https://hub.getdbt.com/calogica/dbt_expectations/latest/)

### Great Expectations
- [Getting Started](https://docs.greatexpectations.io/docs/)
- [Expectations Gallery](https://greatexpectations.io/expectations/)

### Best Practices
- [Data Quality Testing](https://www.getdbt.com/analytics-engineering/transformation/data-testing/)
- [Test Coverage Guidelines](https://docs.getdbt.com/guides/best-practices/writing-effective-tests)

## 🤝 Contributing

To add new tests:

1. Identify the appropriate layer
2. Create test definition (YAML or SQL)
3. Document expected behavior
4. Set appropriate severity
5. Update this README

## 📝 Changelog

### Version 2.0 (Current)
- ✨ Added dbt_expectations integration
- ✨ Added 100+ new data quality tests
- ✨ Enhanced Python test suite
- ✨ Added CI/CD workflow
- ✨ Comprehensive HTML/JSON reporting

### Version 1.0
- Initial test automation framework
- Basic dbt tests
- Simple Python validation

## 📞 Support

For questions or issues:
1. Check troubleshooting section
2. Review test reports for specific failures
3. Consult dbt documentation
4. Contact data engineering team

---

**Last Updated**: February 2026  
**Maintained By**: Data Engineering Team
