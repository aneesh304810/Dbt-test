# Installation and Setup Guide

## 📦 Complete Test Automation Installation

Follow these steps to integrate the full test automation suite into your existing dbt project.

## Prerequisites

- Python 3.9 or higher
- dbt installed and configured
- DuckDB (or your database of choice)
- Git (for version control)

## Step-by-Step Installation

### Step 1: Backup Your Current Project

```bash
# Create a backup of your current dbt project
cp -r dbt_final dbt_final_backup
```

### Step 2: Install Python Dependencies

```bash
# Navigate to your project directory
cd dbt_final

# Install required packages
pip install -r requirements.txt

# Or install manually
pip install dbt-core dbt-duckdb duckdb pandas great-expectations
```

### Step 3: Update dbt Packages

```bash
# Replace your packages.yml with the enhanced version
cp packages.yml packages.yml.backup
cp ../test_automation_suite/packages.yml ./packages.yml

# Install new packages
dbt deps
```

### Step 4: Add Enhanced Schema Files

```bash
# Backup existing schema files
cp models/sources/sei_sources.yml models/sources/sei_sources.yml.backup
cp models/marts/mart_advent.yml models/marts/mart_advent.yml.backup

# Copy enhanced schema files
cp ../test_automation_suite/schemas/sei_sources_enhanced.yml models/sources/sei_sources.yml
cp ../test_automation_suite/schemas/mart_advent_enhanced.yml models/marts/mart_advent.yml
```

### Step 5: Add Custom Test Files

```bash
# Create tests directory if it doesn't exist
mkdir -p tests

# Copy custom SQL tests
cp ../test_automation_suite/tests/*.sql tests/
```

### Step 6: Add Python Test Suite

```bash
# Create python_tests directory
mkdir -p python_tests

# Copy comprehensive test suite
cp ../test_automation_suite/python_tests/comprehensive_test_suite.py python_tests/
```

### Step 7: Set Up Great Expectations (Optional)

```bash
# Run GX setup script
python ../test_automation_suite/great_expectations/setup_gx.py
```

### Step 8: Set Up CI/CD (Optional)

```bash
# Create GitHub Actions directory
mkdir -p .github/workflows

# Copy workflow file
cp ../test_automation_suite/ci_cd/github_actions.yml .github/workflows/test_automation.yml
```

### Step 9: Add Documentation

```bash
# Create docs directory
mkdir -p docs

# Copy comprehensive README
cp ../test_automation_suite/docs/README.md docs/TEST_AUTOMATION.md
```

## Verification

### Step 1: Verify Installation

```bash
# Check dbt packages
dbt deps
dbt list

# Check Python dependencies
python -c "import duckdb, pandas, great_expectations; print('✅ All dependencies installed')"
```

### Step 2: Run Initial Tests

```bash
# Run dbt models
dbt seed
dbt run

# Run basic dbt tests
dbt test --select "tag:critical" || true

# Run comprehensive suite
python python_tests/comprehensive_test_suite.py
```

### Step 3: Review Reports

```bash
# Open HTML report in browser
# reports/comprehensive_test_report_latest.html

# Check JSON report
cat reports/test_report_latest.json | python -m json.tool | head -30
```

## Project Structure After Installation

```
dbt_final/
├── .github/
│   └── workflows/
│       └── test_automation.yml          # CI/CD workflow
├── models/
│   ├── sources/
│   │   └── sei_sources.yml              # ✨ Enhanced with 50+ tests
│   ├── staging/
│   │   └── stg_staging.yml
│   ├── mappings/
│   │   └── map_mappings.yml
│   └── marts/
│       └── mart_advent.yml              # ✨ Enhanced with 100+ tests
├── tests/
│   ├── test_l1_l2_mapping_consistency.sql        # ✨ New
│   ├── test_sei_code_leakage.sql                 # ✨ New
│   ├── test_orphaned_securities.sql              # ✨ New
│   ├── test_fallback_mapping_threshold.sql       # ✨ New
│   ├── test_seed_completeness.sql                # ✨ New
│   └── test_data_type_consistency.sql            # ✨ New
├── python_tests/
│   └── comprehensive_test_suite.py      # ✨ New - Main test orchestrator
├── great_expectations/                  # ✨ New - GX configuration
│   ├── setup_gx.py
│   └── great_expectations.yml
├── reports/                             # ✨ New - Generated reports
│   ├── comprehensive_test_report_latest.html
│   └── test_report_latest.json
├── docs/
│   └── TEST_AUTOMATION.md              # ✨ New - Documentation
├── packages.yml                         # ✨ Updated with test packages
├── requirements.txt                     # ✨ New
└── README.md                           # ✨ Updated
```

## Configuration

### Environment Variables

```bash
# Set database path (optional, defaults to ./dbt_sei_to_advent.duckdb)
export DUCKDB_PATH="/path/to/your/database.duckdb"

# Set dbt profiles directory (optional)
export DBT_PROFILES_DIR="$HOME/.dbt"
```

### Test Thresholds

Edit threshold values in:

1. **Fallback Mapping Thresholds**
   - File: `tests/test_fallback_mapping_threshold.sql`
   - L1 threshold: Line 26 (default: 20%)
   - L2 threshold: Line 41 (default: 25%)

2. **DuckDB Quality Metrics**
   - File: `python_tests/comprehensive_test_suite.py`
   - Function: `define_duckdb_checks()`
   - Various thresholds throughout

3. **CI/CD Quality Gates**
   - File: `.github/workflows/test_automation.yml`
   - Job: `quality-gates`
   - MIN_PASS_RATE: Line 117 (default: 95%)

## Common Issues and Solutions

### Issue: "Module not found" errors

**Solution:**
```bash
pip install --upgrade -r requirements.txt
```

### Issue: "Relation does not exist" in tests

**Solution:**
```bash
# Run models first
dbt seed
dbt run
# Then run tests
dbt test
```

### Issue: Tests fail due to missing data

**Solution:**
```bash
# Load sample data
python scripts/load_sample_data.py

# Or seed from CSV
dbt seed --full-refresh
```

### Issue: Great Expectations setup fails

**Solution:**
```bash
# Install GX separately
pip install great-expectations

# Re-run setup
python great_expectations/setup_gx.py
```

### Issue: CI/CD workflow fails

**Solution:**
1. Check GitHub Actions secrets are set
2. Verify Python version compatibility (3.9-3.11)
3. Review workflow logs for specific errors

## Customization

### Add New Test Categories

1. **dbt Native Tests**: Add to schema YAML files
   ```yaml
   - name: new_column
     tests:
       - not_null
       - unique
   ```

2. **Custom SQL Tests**: Create new SQL file in `tests/`
   ```sql
   -- tests/test_my_custom_check.sql
   select * from {{ ref('my_model') }}
   where condition_fails
   ```

3. **DuckDB Validations**: Add to `define_duckdb_checks()` function

4. **Great Expectations**: Use `setup_gx.py` or GX CLI

### Modify Report Format

Edit HTML template in `comprehensive_test_suite.py`:
- Function: `generate_html_report()`
- Customize CSS styles
- Add/remove sections
- Change color schemes

### Add Email Notifications

Add to CI/CD workflow:
```yaml
- name: Send email notification
  if: failure()
  uses: dawidd6/action-send-mail@v3
  with:
    server_address: smtp.gmail.com
    server_port: 587
    username: ${{ secrets.EMAIL_USERNAME }}
    password: ${{ secrets.EMAIL_PASSWORD }}
    subject: "Test Automation Failed"
    body: "Check GitHub Actions for details"
    to: data-team@example.com
```

## Maintenance

### Regular Tasks

**Daily:**
- Review CI/CD test results
- Investigate any failures

**Weekly:**
- Review fallback mapping rates
- Update seed crosswalks for new codes
- Check data quality trends

**Monthly:**
- Update dbt packages: `dbt deps --upgrade`
- Review and update test thresholds
- Archive old test reports

**Quarterly:**
- Review test coverage
- Add tests for new business rules
- Update documentation

### Updating Test Suite

```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install --upgrade -r requirements.txt
dbt deps

# Test locally
python python_tests/comprehensive_test_suite.py

# Commit changes
git add .
git commit -m "Update test automation suite"
git push
```

## Support and Resources

### Documentation
- **Main README**: `docs/TEST_AUTOMATION.md`
- **dbt Docs**: Run `dbt docs generate && dbt docs serve`
- **GX Data Docs**: `great_expectations/uncommitted/data_docs/local_site/index.html`

### Helpful Commands

```bash
# Run only critical tests
dbt test --select "tag:critical"

# Run specific model tests
dbt test --select "advent_securities"

# Generate test coverage report
dbt test --store-failures

# Run Python suite with options
python python_tests/comprehensive_test_suite.py --help
```

### Getting Help

1. Check troubleshooting section in main README
2. Review test failure messages in reports
3. Consult dbt documentation
4. Contact data engineering team

## Next Steps

After installation:

1. ✅ Run full test suite to establish baseline
2. ✅ Review all test reports
3. ✅ Address any failing tests
4. ✅ Configure CI/CD if needed
5. ✅ Train team on new testing workflows
6. ✅ Schedule regular test reviews
7. ✅ Document any custom modifications

## Rollback Instructions

If you need to revert to the original setup:

```bash
# Restore backup files
cp models/sources/sei_sources.yml.backup models/sources/sei_sources.yml
cp models/marts/mart_advent.yml.backup models/marts/mart_advent.yml
cp packages.yml.backup packages.yml

# Remove new directories
rm -rf tests python_tests great_expectations reports .github/workflows

# Reinstall original packages
dbt deps

# You're back to the original state
```

---

**Installation Complete!** 🎉

You now have a comprehensive, production-ready test automation suite integrated into your dbt project.
