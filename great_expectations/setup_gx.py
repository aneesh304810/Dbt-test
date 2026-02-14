"""
Great Expectations Setup Script for SEI to Advent Transformation

This script initializes Great Expectations for the dbt project and creates
expectations for the advent_securities mart.

Usage:
    python great_expectations/setup_gx.py
"""

import os
import sys
from pathlib import Path

try:
    import great_expectations as gx
    from great_expectations.core.batch import RuntimeBatchRequest
    from great_expectations.data_context.types.base import (
        DataContextConfig,
        DatasourceConfig,
        FilesystemStoreBackendDefaults
    )
except ImportError:
    print("ERROR: great_expectations not installed")
    print("Install with: pip install great-expectations")
    sys.exit(1)

try:
    import duckdb
except ImportError:
    print("ERROR: duckdb not installed")
    print("Install with: pip install duckdb")
    sys.exit(1)


PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GX_DIR = os.path.join(PROJECT_DIR, "great_expectations")
DB_PATH = os.environ.get("DUCKDB_PATH", os.path.join(PROJECT_DIR, "dbt_sei_to_advent.duckdb"))


def initialize_gx_context():
    """Initialize Great Expectations context."""
    print("Initializing Great Expectations context...")
    
    if os.path.exists(GX_DIR):
        print(f"  Great Expectations already initialized at: {GX_DIR}")
        context = gx.get_context(context_root_dir=GX_DIR)
        return context
    
    # Create new context
    context = gx.get_context(context_root_dir=GX_DIR, mode="file")
    print(f"  Created new context at: {GX_DIR}")
    return context


def add_duckdb_datasource(context):
    """Add DuckDB datasource to Great Expectations."""
    print("\nConfiguring DuckDB datasource...")
    
    datasource_name = "sei_to_advent_duckdb"
    
    # Check if datasource already exists
    try:
        datasource = context.get_datasource(datasource_name)
        print(f"  Datasource '{datasource_name}' already exists")
        return datasource
    except:
        pass
    
    # Create new datasource
    datasource_config = {
        "name": datasource_name,
        "class_name": "Datasource",
        "execution_engine": {
            "class_name": "SqlAlchemyExecutionEngine",
            "connection_string": f"duckdb:///{DB_PATH}",
        },
        "data_connectors": {
            "default_runtime_data_connector": {
                "class_name": "RuntimeDataConnector",
                "batch_identifiers": ["default_identifier_name"],
            },
        },
    }
    
    datasource = context.add_datasource(**datasource_config)
    print(f"  Created datasource: {datasource_name}")
    return datasource


def create_expectations_suite(context, datasource):
    """Create expectations suite for advent_securities."""
    print("\nCreating expectations suite...")
    
    suite_name = "advent_securities_suite"
    
    # Create or get existing suite
    try:
        suite = context.get_expectation_suite(suite_name)
        print(f"  Suite '{suite_name}' already exists")
    except:
        suite = context.create_expectation_suite(suite_name)
        print(f"  Created suite: {suite_name}")
    
    # Create batch request
    batch_request = RuntimeBatchRequest(
        datasource_name=datasource.name,
        data_connector_name="default_runtime_data_connector",
        data_asset_name="advent_securities",
        runtime_parameters={"query": "SELECT * FROM main_marts.advent_securities"},
        batch_identifiers={"default_identifier_name": "default_identifier"},
    )
    
    # Get validator
    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name=suite_name,
    )
    
    # Add expectations
    expectations_added = 0
    
    # Primary Key Expectations
    validator.expect_column_values_to_be_unique(column="SECURITY_ID")
    validator.expect_column_values_to_not_be_null(column="SECURITY_ID")
    expectations_added += 2
    
    # Completeness Expectations
    for col in ["SECURITY_NAME", "ASSET_CLASS_CODE", "ASSET_CLASS", 
                "STRATEGY_CODE", "STRATEGY_DESCRIPTION", "SECURITY_TYPE", "STATUS"]:
        validator.expect_column_values_to_not_be_null(column=col)
        expectations_added += 1
    
    # Format Expectations
    validator.expect_column_value_lengths_to_equal(
        column="BASE_CURRENCY",
        value=3,
        mostly=0.99
    )
    validator.expect_column_value_lengths_to_equal(
        column="COUNTRY_CODE",
        value=2,
        mostly=0.99
    )
    validator.expect_column_value_lengths_to_equal(
        column="CUSIP",
        value=9,
        mostly=0.99
    )
    expectations_added += 3
    
    # Value Set Expectations
    validator.expect_column_values_to_be_in_set(
        column="STATUS",
        value_set=["A", "I", "U"]
    )
    validator.expect_column_values_to_be_in_set(
        column="SECURITY_TYPE",
        value_set=["EQUITY", "FIXED_INCOME", "OPTION", "FUTURE", 
                   "CASH_EQUIV", "CONVERTIBLE", "PREFERRED", "ALTERNATIVE", "OTHER"]
    )
    validator.expect_column_values_to_be_in_set(
        column="_L1_MAPPING_METHOD",
        value_set=["DIRECT", "PARENT_ROLLUP", "FALLBACK"]
    )
    validator.expect_column_values_to_be_in_set(
        column="_L2_MAPPING_METHOD",
        value_set=["DIRECT", "ASSET_CLASS_DEFAULT", "FALLBACK"]
    )
    expectations_added += 4
    
    # Range Expectations
    validator.expect_column_values_to_be_between(
        column="PRICE",
        min_value=0,
        max_value=1000000,
        mostly=0.99
    )
    validator.expect_column_values_to_be_between(
        column="COUPON_RATE",
        min_value=0,
        max_value=0.50,
        mostly=0.99
    )
    expectations_added += 2
    
    # Pattern Matching Expectations
    validator.expect_column_values_to_match_regex(
        column="BASE_CURRENCY",
        regex="^[A-Z]{3}$",
        mostly=0.99
    )
    validator.expect_column_values_to_match_regex(
        column="COUNTRY_CODE",
        regex="^[A-Z]{2}$",
        mostly=0.99
    )
    expectations_added += 2
    
    # Statistical Expectations
    validator.expect_table_row_count_to_be_between(
        min_value=100,
        max_value=1000000
    )
    validator.expect_column_proportion_of_unique_values_to_be_between(
        column="SECURITY_ID",
        min_value=0.99,
        max_value=1.0
    )
    expectations_added += 2
    
    # Save expectations
    validator.save_expectation_suite(discard_failed_expectations=False)
    
    print(f"  Added {expectations_added} expectations to suite")
    return suite


def create_checkpoint(context):
    """Create checkpoint for validation."""
    print("\nCreating validation checkpoint...")
    
    checkpoint_name = "sei_to_advent_checkpoint"
    
    checkpoint_config = {
        "name": checkpoint_name,
        "config_version": 1.0,
        "class_name": "SimpleCheckpoint",
        "run_name_template": "%Y%m%d-%H%M%S-sei-to-advent",
        "validations": [
            {
                "batch_request": {
                    "datasource_name": "sei_to_advent_duckdb",
                    "data_connector_name": "default_runtime_data_connector",
                    "data_asset_name": "advent_securities",
                    "runtime_parameters": {
                        "query": "SELECT * FROM main_marts.advent_securities"
                    },
                    "batch_identifiers": {
                        "default_identifier_name": "default_identifier"
                    },
                },
                "expectation_suite_name": "advent_securities_suite",
            }
        ],
    }
    
    try:
        context.add_checkpoint(**checkpoint_config)
        print(f"  Created checkpoint: {checkpoint_name}")
    except:
        print(f"  Checkpoint '{checkpoint_name}' already exists")


def test_checkpoint(context):
    """Test the checkpoint by running it."""
    print("\nTesting checkpoint...")
    
    try:
        result = context.run_checkpoint(checkpoint_name="sei_to_advent_checkpoint")
        
        if result.success:
            print("  ✅ Checkpoint validation PASSED")
        else:
            print("  ❌ Checkpoint validation FAILED")
            print(f"  See results in: {GX_DIR}/uncommitted/data_docs/")
        
        return result
    except Exception as e:
        print(f"  ⚠️  Could not run checkpoint: {e}")
        print("  This is expected if dbt models haven't been run yet")
        return None


def build_data_docs(context):
    """Build Data Docs."""
    print("\nBuilding Data Docs...")
    
    try:
        context.build_data_docs()
        docs_path = os.path.join(GX_DIR, "uncommitted", "data_docs", "local_site", "index.html")
        print(f"  📊 Data Docs built at: {docs_path}")
    except Exception as e:
        print(f"  ⚠️  Could not build Data Docs: {e}")


def main():
    """Main setup function."""
    print("=" * 80)
    print("  Great Expectations Setup for SEI to Advent Transformation")
    print("=" * 80)
    print(f"  Project Directory: {PROJECT_DIR}")
    print(f"  Database: {DB_PATH}")
    print("=" * 80)
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"\n⚠️  WARNING: Database not found at {DB_PATH}")
        print("  Please run dbt models first:")
        print("    dbt seed")
        print("    dbt run")
        print("\n  Continuing with setup anyway...")
    
    # Initialize context
    context = initialize_gx_context()
    
    # Add datasource
    datasource = add_duckdb_datasource(context)
    
    # Create expectations
    suite = create_expectations_suite(context, datasource)
    
    # Create checkpoint
    create_checkpoint(context)
    
    # Test checkpoint (if data available)
    if os.path.exists(DB_PATH):
        test_checkpoint(context)
    
    # Build Data Docs
    build_data_docs(context)
    
    print("\n" + "=" * 80)
    print("  ✅ Great Expectations setup complete!")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Review expectations in the suite")
    print("  2. Run checkpoint: context.run_checkpoint('sei_to_advent_checkpoint')")
    print("  3. View Data Docs in browser")
    print(f"  4. Integrate into test suite: python_tests/comprehensive_test_suite.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
