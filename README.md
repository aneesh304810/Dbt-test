# 🔬 SEI to Advent - Complete Test Automation Suite

> **Production-ready, comprehensive test automation for dbt data transformation pipelines**

## 🎯 Overview

This is a **complete, enterprise-grade test automation suite** designed to ensure data quality, integrity, and accuracy in your SEI to Advent Advantage transformation pipeline. It provides **4 layers of validation** with **200+ automated tests** covering every aspect of your data transformation.

### Key Features

- ✅ **200+ Automated Tests** across 4 validation layers
- 📊 **Beautiful HTML Reports** with visual metrics and drill-down capability
- 🤖 **CI/CD Integration** with GitHub Actions
- 🔍 **Great Expectations** integration for advanced statistical validation
- 📈 **Quality Metrics** and threshold monitoring
- 🚨 **Real-time Alerting** for data quality issues
- 📚 **Comprehensive Documentation** with examples and best practices

## 📦 What's Included

### 1. Enhanced dbt Schema Files (150+ tests)

**`schemas/sei_sources_enhanced.yml`**
- 50+ source data quality tests
- Format validation (CUSIP, ISIN, SEDOL, currencies, dates)
- Referential integrity checks
- Freshness monitoring
- Data completeness validation

**`schemas/mart_advent_enhanced.yml`**
- 100+ mart output tests
- All identifier format validation
- Business rule validation
- Mapping integrity checks
- Range and pattern validation
- Statistical anomaly detection

### 2. Custom SQL Tests (6 critical tests)

| Test | Purpose | Impact |
|------|---------|--------|
| `test_l1_l2_mapping_consistency.sql` | Validates strategy-to-asset-class alignment | **Critical** - Prevents misconfigured hierarchies |
| `test_sei_code_leakage.sql` | Ensures no SEI codes in Advent output | **Critical** - Maintains data contract |
| `test_orphaned_securities.sql` | Detects data loss or phantom records | **Critical** - Ensures completeness |
| `test_fallback_mapping_threshold.sql` | Monitors mapping quality metrics | **High** - Quality monitoring |
| `test_seed_completeness.sql` | Validates crosswalk coverage | **High** - Proactive issue detection |
| `test_data_type_consistency.sql` | Ensures type safety across pipeline | **Medium** - Data integrity |

### 3. Python Validation Suite

**`python_tests/comprehensive_test_suite.py`**
- Orchestrates all test layers
- 25+ DuckDB custom validations
- Schema validation
- Row count reconciliation
- Format checks
- Business rule validation
- Quality metrics calculation
- HTML and JSON report generation
- CI/CD integration support

### 4. Great Expectations Integration

**`great_expectations/setup_gx.py`**
- Automated GX setup and configuration
- 20+ statistical expectations
- Distribution analysis
- Anomaly detection
- Historical comparisons
- Data Docs generation

### 5. CI/CD Workflow

**`ci_cd/github_actions.yml`**
- Automated testing on push/PR
- Scheduled daily runs
- Quality gate enforcement
- Test report artifacts
- Automatic PR comments
- dbt docs deployment

### 6. Documentation

**`docs/README.md`** - Comprehensive usage guide  
**`INSTALLATION_GUIDE.md`** - Step-by-step setup instructions  
**`requirements.txt`** - Python dependencies

## 🚀 Quick Start

### Installation

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install dbt packages
dbt deps

# 3. Set up Great Expectations (optional)
python great_expectations/setup_gx.py
```

### Run Tests

```bash
# Full test suite (recommended)
python python_tests/comprehensive_test_suite.py

# View reports
open reports/comprehensive_test_report_latest.html
```

## 📊 Test Coverage Summary

### By Layer

| Layer | Tests | Coverage |
|-------|-------|----------|
| **dbt Native Tests** | 150+ | Schema, integrity, completeness, validity |
| **Custom SQL Tests** | 6 | Business rules, quality metrics |
| **DuckDB Validations** | 25+ | Reconciliation, formats, leakage |
| **Great Expectations** | 20+ | Statistical validation, anomalies |
| **TOTAL** | **200+** | **Comprehensive coverage** |

### By Category

```
Uniqueness ████████████████████ 20 tests
Completeness ████████████████████████████ 35 tests
Validity ████████████████████████ 30 tests
Referential Integrity ████████████████ 18 tests
Format ██████████████████████ 25 tests
Reconciliation ████████████ 12 tests
Business Rules ████████████████ 15 tests
Quality Metrics ███████████ 10 tests
Data Leakage █████████ 8 tests
Range Validation ██████████ 12 tests
Statistical ████████████ 15 tests
```

## 🎯 Test Results Example

```
┌─────────────────────────────────────────────────────────┐
│         SEI to Advent Test Report - ✅ PASSED           │
├─────────────────────────────────────────────────────────┤
│  Total Tests:      203                                  │
│  Passed:          201  (99.0%)                          │
│  Failed:            2  (1.0%)                           │
│  Warned:            0                                   │
├─────────────────────────────────────────────────────────┤
│  dbt Tests:        149/150 passed                       │
│  DuckDB:           24/25 passed                         │
│  Great Expect.:    20/20 passed                         │
├─────────────────────────────────────────────────────────┤
│  L1 FALLBACK:      8.2%  ✅ (< 20% threshold)           │
│  L2 FALLBACK:      12.5% ✅ (< 25% threshold)           │
│  Data Loss:        0     ✅                             │
│  SEI Leakage:      0     ✅                             │
└─────────────────────────────────────────────────────────┘
```

## 📁 File Structure

```
test_automation_suite/
├── schemas/                          # Enhanced dbt schema files
│   ├── sei_sources_enhanced.yml      # 50+ source tests
│   └── mart_advent_enhanced.yml      # 100+ mart tests
├── tests/                            # Custom SQL tests
│   ├── test_l1_l2_mapping_consistency.sql
│   ├── test_sei_code_leakage.sql
│   ├── test_orphaned_securities.sql
│   ├── test_fallback_mapping_threshold.sql
│   ├── test_seed_completeness.sql
│   └── test_data_type_consistency.sql
├── python_tests/                     # Python test suite
│   └── comprehensive_test_suite.py   # Main orchestrator
├── great_expectations/               # GX configuration
│   └── setup_gx.py                   # Automated setup
├── ci_cd/                           # CI/CD integration
│   └── github_actions.yml           # GitHub workflow
├── docs/                            # Documentation
│   └── README.md                    # Usage guide
├── packages.yml                     # Enhanced dbt packages
├── requirements.txt                 # Python dependencies
├── INSTALLATION_GUIDE.md           # Setup instructions
└── README.md                       # This file
```

## 🔧 Configuration Options

### Run Selective Tests

```bash
# Run only critical tests
python python_tests/comprehensive_test_suite.py --selector "tag:critical"

# Skip Great Expectations
python python_tests/comprehensive_test_suite.py --skip-gx

# Skip DuckDB validations
python python_tests/comprehensive_test_suite.py --skip-duckdb

# dbt only
dbt test
```

### Adjust Thresholds

Edit threshold values in:
- `tests/test_fallback_mapping_threshold.sql` (L1/L2 fallback %)
- `python_tests/comprehensive_test_suite.py` (DuckDB checks)
- `.github/workflows/test_automation.yml` (CI/CD quality gates)

## 📈 Quality Metrics Tracked

### Mapping Quality
- **Direct Mapping Rate**: % using exact crosswalk matches
- **Fallback Rate**: % using default/fallback values
- **Parent Rollup Rate**: % using hierarchical mapping

### Data Completeness
- **Coverage**: % records with all required fields
- **Identifier Coverage**: % with CUSIP/ISIN
- **Pricing Coverage**: % with valid pricing data

### Data Integrity
- **Orphan Rate**: Records lost/gained in transformation
- **Referential Integrity**: % with valid foreign keys
- **Uniqueness**: Duplicate detection

### Business Rules
- **L1/L2 Consistency**: Strategy-to-asset class alignment
- **SEI Leakage**: Unwanted code patterns
- **Status Accuracy**: Active/inactive validation

## 🚨 Alerting and Monitoring

### CI/CD Integration

The GitHub Actions workflow automatically:
- ✅ Runs on every push/PR
- ✅ Runs daily at 6 AM UTC
- ✅ Enforces quality gates (95% pass rate)
- ✅ Posts results as PR comments
- ✅ Uploads test reports as artifacts
- ✅ Deploys dbt docs to GitHub Pages

### Quality Gates

Tests fail CI/CD if:
- Pass rate < 95%
- L1 fallback > 20%
- L2 fallback > 25%
- Any critical test fails

## 📚 Documentation

### Included Documentation

1. **README.md** (this file) - Overview and quick start
2. **INSTALLATION_GUIDE.md** - Detailed setup instructions
3. **docs/README.md** - Comprehensive usage guide
4. **In-code comments** - Detailed explanations in all files

### External Resources

- [dbt Testing Guide](https://docs.getdbt.com/docs/building-a-dbt-project/tests)
- [dbt_expectations Package](https://hub.getdbt.com/calogica/dbt_expectations/latest/)
- [Great Expectations Docs](https://docs.greatexpectations.io/)

## 🎓 Learning Path

### Beginner
1. Review `INSTALLATION_GUIDE.md`
2. Run basic dbt tests: `dbt test`
3. Examine failing tests
4. Review HTML reports

### Intermediate
5. Run full Python suite
6. Understand each test layer
7. Modify thresholds
8. Add custom tests

### Advanced
9. Set up Great Expectations
10. Configure CI/CD pipeline
11. Create custom expectations
12. Build team dashboards

## 🔄 Maintenance

### Regular Tasks

**Daily** (automated via CI/CD):
- Monitor test results
- Investigate failures
- Update mappings if needed

**Weekly**:
- Review quality metrics trends
- Update seed crosswalks
- Address warned tests

**Monthly**:
- Update dbt packages
- Review test coverage
- Adjust thresholds based on trends

## 🤝 Contributing

### Adding New Tests

1. **dbt Native**: Add to schema YAML files
2. **Custom SQL**: Create `.sql` file in `tests/`
3. **DuckDB**: Add to `define_duckdb_checks()` function
4. **Great Expectations**: Use GX CLI or modify setup script

### Reporting Issues

When reporting test failures:
- Include test name and category
- Attach HTML report
- Provide data samples (if not sensitive)
- Describe expected vs. actual behavior

## 🎯 Success Criteria

Your test automation is working well when:

✅ All tests pass consistently  
✅ New issues are caught before production  
✅ Fallback rates remain low (< 10%)  
✅ No SEI code leakage detected  
✅ Zero data loss (orphan rate = 0)  
✅ CI/CD pipeline is green  
✅ Team reviews test reports regularly

## 💡 Best Practices

1. **Run tests locally before committing**
2. **Review reports after every change**
3. **Update seeds proactively**
4. **Monitor quality trends weekly**
5. **Document test failures**
6. **Keep thresholds realistic**
7. **Test with realistic data volumes**

## 🐛 Troubleshooting

See `INSTALLATION_GUIDE.md` for common issues and solutions.

Quick fixes:
- **"Relation not found"**: Run `dbt run` first
- **"Module not found"**: Run `pip install -r requirements.txt`
- **High execution time**: Use selective test runs
- **Database locked**: Check for other dbt processes

## 📞 Support

For questions or issues:
1. Check documentation in `docs/`
2. Review troubleshooting guide
3. Examine test reports for details
4. Contact data engineering team

## 🏆 Credits

Built with:
- [dbt](https://www.getdbt.com/)
- [dbt_utils](https://hub.getdbt.com/dbt-labs/dbt_utils/latest/)
- [dbt_expectations](https://hub.getdbt.com/calogica/dbt_expectations/latest/)
- [Great Expectations](https://greatexpectations.io/)
- [DuckDB](https://duckdb.org/)

## 📝 License

This test automation suite is provided as-is for use with your dbt project.

---

## ⚡ Quick Commands Reference

```bash
# Installation
pip install -r requirements.txt
dbt deps

# Run tests
python python_tests/comprehensive_test_suite.py    # Full suite
dbt test                                           # dbt only
dbt test --select "tag:critical"                   # Critical only

# View reports
open reports/comprehensive_test_report_latest.html
cat reports/test_report_latest.json | jq

# CI/CD
git add .github/workflows/test_automation.yml
git commit -m "Add test automation"
git push

# Great Expectations
python great_expectations/setup_gx.py
```

---

**Ready to ensure data quality?** Start with the [Installation Guide](INSTALLATION_GUIDE.md)! 🚀
