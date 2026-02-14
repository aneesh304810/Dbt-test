"""
Comprehensive Test Automation Suite for SEI to Advent Transformation
Integrates dbt tests, DuckDB validations, and Great Expectations

Usage:
    python python_tests/comprehensive_test_suite.py
    
Features:
    - Runs dbt native tests
    - Executes custom SQL validations
    - Performs Great Expectations data quality checks
    - Generates detailed HTML and JSON reports
    - Supports CI/CD integration
"""

import subprocess
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    print("WARNING: duckdb not installed. Database validations will be skipped.")

try:
    import great_expectations as gx
    from great_expectations.core.batch import RuntimeBatchRequest
    GX_AVAILABLE = True
except ImportError:
    GX_AVAILABLE = False
    print("WARNING: great_expectations not installed. GX validations will be skipped.")

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("WARNING: pandas not installed. Some validations will be skipped.")


# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.environ.get("DUCKDB_PATH", os.path.join(PROJECT_DIR, "dbt_sei_to_advent.duckdb"))
REPORTS_DIR = os.path.join(PROJECT_DIR, "reports")
GX_DIR = os.path.join(PROJECT_DIR, "great_expectations")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

os.makedirs(REPORTS_DIR, exist_ok=True)


# ============================================================================
# DBT TEST EXECUTION
# ============================================================================

def run_dbt_tests(test_selector: str = None) -> Tuple[List[Dict], Dict]:
    """
    Run dbt tests and parse results.
    
    Args:
        test_selector: Optional selector for specific tests (e.g., 'tag:critical')
    
    Returns:
        Tuple of (test_results_list, summary_dict)
    """
    print("\n" + "=" * 80)
    print("  PHASE 1: dbt Native Tests")
    print("=" * 80)
    
    results = []
    summary = {"passed": 0, "failed": 0, "warned": 0, "errored": 0, "skipped": 0}
    
    try:
        cmd = ["dbt", "test", "--project-dir", PROJECT_DIR]
        if test_selector:
            cmd.extend(["--select", test_selector])
        
        print(f"  Running: {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_DIR)
        
        # Parse run_results.json
        run_results_path = os.path.join(PROJECT_DIR, "target", "run_results.json")
        if os.path.exists(run_results_path):
            with open(run_results_path) as f:
                data = json.load(f)
            
            for r in data.get("results", []):
                unique_id = r.get("unique_id", "")
                name = unique_id.replace("test.", "")
                status = r.get("status", "error")
                
                result = {
                    "name": name,
                    "unique_id": unique_id,
                    "status": status,
                    "message": r.get("message", ""),
                    "failures": r.get("failures", 0),
                    "execution_time": round(r.get("execution_time", 0), 3),
                    "category": categorize_test(name),
                    "adapter_response": r.get("adapter_response", {})
                }
                
                results.append(result)
                
                if status == "pass":
                    summary["passed"] += 1
                elif status == "fail":
                    summary["failed"] += 1
                elif status == "warn":
                    summary["warned"] += 1
                elif status == "skipped":
                    summary["skipped"] += 1
                else:
                    summary["errored"] += 1
        
        print(f"  Results: {summary['passed']} passed | {summary['failed']} failed | "
              f"{summary['warned']} warned | {summary['errored']} errored | "
              f"{summary['skipped']} skipped")
        print(f"  Total execution time: {sum(r['execution_time'] for r in results):.2f}s")
    
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({
            "name": "dbt_execution_error",
            "status": "error",
            "message": str(e),
            "execution_time": 0,
            "category": "Execution"
        })
        summary["errored"] += 1
    
    return results, summary


def categorize_test(test_name: str) -> str:
    """Categorize test by type based on name."""
    name_lower = test_name.lower()
    
    if "unique" in name_lower:
        return "Uniqueness"
    elif "not_null" in name_lower:
        return "Completeness"
    elif "accepted_values" in name_lower or "values_in_set" in name_lower:
        return "Validity"
    elif "relationship" in name_lower:
        return "Referential Integrity"
    elif "rowcount" in name_lower or "reconcil" in name_lower:
        return "Reconciliation"
    elif "format" in name_lower or "regex" in name_lower or "length" in name_lower:
        return "Format"
    elif "range" in name_lower or "between" in name_lower:
        return "Range"
    elif "leakage" in name_lower:
        return "Data Leakage"
    elif "orphan" in name_lower:
        return "Orphans"
    elif "fallback" in name_lower or "threshold" in name_lower:
        return "Quality Metrics"
    elif "seed" in name_lower or "completeness" in name_lower:
        return "Seed Coverage"
    else:
        return "Other"


# ============================================================================
# DUCKDB VALIDATIONS
# ============================================================================

def run_duckdb_validations() -> Tuple[List[Dict], Dict]:
    """Execute custom DuckDB data quality checks."""
    print("\n" + "=" * 80)
    print("  PHASE 2: DuckDB Custom Validations")
    print("=" * 80)
    
    results = []
    summary = {"passed": 0, "failed": 0}
    
    if not DUCKDB_AVAILABLE:
        print("  SKIPPED: DuckDB not installed")
        return results, summary
    
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        
        # Define validation checks
        checks = define_duckdb_checks()
        
        for check_name, query, check_fn, severity in checks:
            try:
                value = con.execute(query).fetchone()[0]
                passed = check_fn(value)
                
                result = {
                    "name": check_name,
                    "status": "passed" if passed else "failed",
                    "observed": str(value),
                    "category": check_name.split(":")[0].strip(),
                    "severity": severity
                }
                
                results.append(result)
                
                if passed:
                    summary["passed"] += 1
                else:
                    summary["failed"] += 1
                    if severity == "critical":
                        print(f"  CRITICAL FAILURE: {check_name} - observed: {value}")
            
            except Exception as e:
                results.append({
                    "name": check_name,
                    "status": "error",
                    "observed": str(e),
                    "category": "Error",
                    "severity": "error"
                })
                summary["failed"] += 1
                print(f"  ERROR in {check_name}: {e}")
        
        con.close()
        print(f"  Results: {summary['passed']} passed | {summary['failed']} failed")
    
    except Exception as e:
        print(f"  ERROR: Unable to connect to database: {e}")
        results.append({
            "name": "database_connection",
            "status": "error",
            "observed": str(e),
            "category": "Infrastructure",
            "severity": "critical"
        })
        summary["failed"] += 1
    
    return results, summary


def define_duckdb_checks() -> List[Tuple]:
    """
    Define DuckDB validation checks.
    
    Returns:
        List of tuples: (name, query, check_function, severity)
    """
    return [
        # ===== SCHEMA VALIDATION =====
        (
            "Schema: All required columns exist in mart",
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema='main_marts' AND table_name='advent_securities'
            AND column_name IN ('SECURITY_ID', 'ASSET_CLASS_CODE', 'STRATEGY_CODE',
                                'STRATEGY_DESCRIPTION', '_L1_MAPPING_METHOD', '_L2_MAPPING_METHOD')
            """,
            lambda v: v == 6,
            "critical"
        ),
        
        # ===== ROW COUNT RECONCILIATION =====
        (
            "Reconciliation: Mart row count matches source",
            """
            SELECT ABS(
                (SELECT COUNT(*) FROM main_marts.advent_securities) -
                (SELECT COUNT(*) FROM raw_sei.securities)
            )
            """,
            lambda v: v == 0,
            "critical"
        ),
        (
            "Reconciliation: Mart row count matches staging",
            """
            SELECT ABS(
                (SELECT COUNT(*) FROM main_marts.advent_securities) -
                (SELECT COUNT(*) FROM main_staging.stg_sei_securities)
            )
            """,
            lambda v: v == 0,
            "critical"
        ),
        (
            "Reconciliation: No duplicate SECURITY_IDs in mart",
            """
            SELECT COUNT(*) - COUNT(DISTINCT SECURITY_ID)
            FROM main_marts.advent_securities
            """,
            lambda v: v == 0,
            "critical"
        ),
        
        # ===== COMPLETENESS CHECKS =====
        (
            "Completeness: No NULL SECURITY_ID",
            "SELECT COUNT(*) FROM main_marts.advent_securities WHERE SECURITY_ID IS NULL",
            lambda v: v == 0,
            "critical"
        ),
        (
            "Completeness: No NULL ASSET_CLASS_CODE",
            "SELECT COUNT(*) FROM main_marts.advent_securities WHERE ASSET_CLASS_CODE IS NULL",
            lambda v: v == 0,
            "critical"
        ),
        (
            "Completeness: No NULL STRATEGY_CODE",
            "SELECT COUNT(*) FROM main_marts.advent_securities WHERE STRATEGY_CODE IS NULL",
            lambda v: v == 0,
            "critical"
        ),
        (
            "Completeness: All securities have SECURITY_NAME",
            "SELECT COUNT(*) FROM main_marts.advent_securities WHERE SECURITY_NAME IS NULL OR SECURITY_NAME = ''",
            lambda v: v == 0,
            "high"
        ),
        
        # ===== FORMAT VALIDATION =====
        (
            "Format: BASE_CURRENCY is 3 characters",
            """
            SELECT COUNT(*) FROM main_marts.advent_securities
            WHERE BASE_CURRENCY IS NOT NULL AND LENGTH(BASE_CURRENCY) != 3
            """,
            lambda v: v == 0,
            "high"
        ),
        (
            "Format: COUNTRY_CODE is 2 characters",
            """
            SELECT COUNT(*) FROM main_marts.advent_securities
            WHERE COUNTRY_CODE IS NOT NULL AND LENGTH(COUNTRY_CODE) != 2
            """,
            lambda v: v == 0,
            "high"
        ),
        (
            "Format: CUSIP is 9 characters",
            """
            SELECT COUNT(*) FROM main_marts.advent_securities
            WHERE CUSIP IS NOT NULL AND LENGTH(CUSIP) != 9
            """,
            lambda v: v == 0,
            "medium"
        ),
        
        # ===== DATA LEAKAGE PREVENTION =====
        (
            "Leakage: No SEI underscore patterns in ASSET_CLASS",
            """
            SELECT COUNT(*) FROM main_marts.advent_securities
            WHERE ASSET_CLASS LIKE '%\_%'
            """,
            lambda v: v == 0,
            "critical"
        ),
        (
            "Leakage: No SEI code patterns in business columns",
            """
            SELECT COUNT(*) FROM main_marts.advent_securities
            WHERE ASSET_CLASS LIKE '%EQ_DOM%'
               OR ASSET_CLASS LIKE '%FI_GOV%'
               OR ASSET_CLASS LIKE '%ALT_HF%'
               OR STRATEGY_DESCRIPTION LIKE '%SEI%'
            """,
            lambda v: v == 0,
            "critical"
        ),
        
        # ===== MAPPING QUALITY METRICS =====
        (
            "Quality: L1 FALLBACK rate < 20%",
            """
            SELECT CASE
                WHEN (SELECT COUNT(*) FROM main_marts.advent_securities WHERE _L1_MAPPING_METHOD = 'FALLBACK') * 100.0 /
                     NULLIF((SELECT COUNT(*) FROM main_marts.advent_securities), 0) > 20
                THEN 1 ELSE 0
            END
            """,
            lambda v: v == 0,
            "high"
        ),
        (
            "Quality: L2 FALLBACK rate < 25%",
            """
            SELECT CASE
                WHEN (SELECT COUNT(*) FROM main_marts.advent_securities WHERE _L2_MAPPING_METHOD = 'FALLBACK') * 100.0 /
                     NULLIF((SELECT COUNT(*) FROM main_marts.advent_securities), 0) > 25
                THEN 1 ELSE 0
            END
            """,
            lambda v: v == 0,
            "high"
        ),
        (
            "Quality: DIRECT L1 mappings > 80%",
            """
            SELECT (SELECT COUNT(*) FROM main_marts.advent_securities WHERE _L1_MAPPING_METHOD = 'DIRECT') * 100.0 /
                   NULLIF((SELECT COUNT(*) FROM main_marts.advent_securities), 0)
            """,
            lambda v: v > 80,
            "medium"
        ),
        
        # ===== REFERENTIAL INTEGRITY =====
        (
            "Integrity: All ASSET_CLASS_CODE values exist in seed",
            """
            SELECT COUNT(*) FROM main_marts.advent_securities m
            LEFT JOIN main.seed_asset_class_crosswalk s
                ON m.ASSET_CLASS_CODE = s.advent_asset_class_code
            WHERE s.advent_asset_class_code IS NULL
            """,
            lambda v: v == 0,
            "critical"
        ),
        (
            "Integrity: All STRATEGY_CODE values exist in seed",
            """
            SELECT COUNT(*) FROM main_marts.advent_securities m
            LEFT JOIN main.seed_strategy_crosswalk s
                ON m.STRATEGY_CODE = s.advent_strategy_code
            WHERE s.advent_strategy_code IS NULL
            """,
            lambda v: v == 0,
            "critical"
        ),
        
        # ===== BUSINESS RULE VALIDATION =====
        (
            "Business Rule: L1/L2 consistency",
            """
            SELECT COUNT(*) FROM main_marts.advent_securities m
            JOIN main.seed_strategy_crosswalk s
                ON m.STRATEGY_CODE = s.advent_strategy_code
            WHERE m.ASSET_CLASS_CODE != s.advent_asset_class_code
            """,
            lambda v: v == 0,
            "critical"
        ),
        (
            "Business Rule: Active securities have valid prices",
            """
            SELECT COUNT(*) FROM main_marts.advent_securities
            WHERE STATUS = 'A' AND (PRICE IS NULL OR PRICE <= 0)
            """,
            lambda v: v == 0,
            "medium"
        ),
        
        # ===== DATA QUALITY METRICS =====
        (
            "Coverage: At least 95% securities have CUSIP or ISIN",
            """
            SELECT (SELECT COUNT(*) FROM main_marts.advent_securities WHERE CUSIP IS NOT NULL OR ISIN IS NOT NULL) * 100.0 /
                   NULLIF((SELECT COUNT(*) FROM main_marts.advent_securities), 0)
            """,
            lambda v: v >= 95,
            "medium"
        ),
        (
            "Coverage: At least 90% securities have pricing data",
            """
            SELECT (SELECT COUNT(*) FROM main_marts.advent_securities WHERE PRICE IS NOT NULL) * 100.0 /
                   NULLIF((SELECT COUNT(*) FROM main_marts.advent_securities), 0)
            """,
            lambda v: v >= 90,
            "medium"
        ),
    ]


# ============================================================================
# GREAT EXPECTATIONS INTEGRATION
# ============================================================================

def run_great_expectations() -> Tuple[List[Dict], Dict]:
    """Execute Great Expectations validations."""
    print("\n" + "=" * 80)
    print("  PHASE 3: Great Expectations Validations")
    print("=" * 80)
    
    results = []
    summary = {"passed": 0, "failed": 0}
    
    if not GX_AVAILABLE or not PANDAS_AVAILABLE:
        print("  SKIPPED: Great Expectations or pandas not installed")
        return results, summary
    
    try:
        # Initialize or load GX context
        if not os.path.exists(GX_DIR):
            print("  Great Expectations not configured. Skipping.")
            return results, summary
        
        context = gx.get_context(context_root_dir=GX_DIR)
        
        # Run checkpoints
        checkpoint_names = ["sei_to_advent_checkpoint"]  # Add your checkpoint names
        
        for checkpoint_name in checkpoint_names:
            try:
                result = context.run_checkpoint(checkpoint_name=checkpoint_name)
                
                if result.success:
                    summary["passed"] += 1
                else:
                    summary["failed"] += 1
                
                results.append({
                    "name": f"GX Checkpoint: {checkpoint_name}",
                    "status": "passed" if result.success else "failed",
                    "category": "Great Expectations",
                    "details": str(result)
                })
            
            except Exception as e:
                print(f"  ERROR running checkpoint {checkpoint_name}: {e}")
                results.append({
                    "name": f"GX Checkpoint: {checkpoint_name}",
                    "status": "error",
                    "category": "Great Expectations",
                    "details": str(e)
                })
                summary["failed"] += 1
        
        print(f"  Results: {summary['passed']} passed | {summary['failed']} failed")
    
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({
            "name": "great_expectations_execution",
            "status": "error",
            "category": "Infrastructure",
            "details": str(e)
        })
        summary["failed"] += 1
    
    return results, summary


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_html_report(
    dbt_results: List[Dict],
    dbt_summary: Dict,
    db_results: List[Dict],
    db_summary: Dict,
    gx_results: List[Dict],
    gx_summary: Dict
) -> str:
    """Generate comprehensive HTML report."""
    
    total_passed = dbt_summary["passed"] + db_summary["passed"] + gx_summary["passed"]
    total_failed = (dbt_summary["failed"] + dbt_summary.get("errored", 0) +
                   db_summary["failed"] + gx_summary["failed"])
    total_warned = dbt_summary.get("warned", 0)
    total_tests = total_passed + total_failed + total_warned
    
    status = "PASSED" if total_failed == 0 else "FAILED"
    status_color = "#27ae60" if status == "PASSED" else "#e74c3c"
    pass_pct = round(total_passed / max(total_tests, 1) * 100, 1)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEI to Advent Test Report - {TIMESTAMP}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
            color: #2d3748;
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        
        .header {{
            background: linear-gradient(135deg, #1a365d, #2c5282);
            color: #fff;
            padding: 32px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
        .header .subtitle {{ opacity: 0.85; font-size: 14px; }}
        
        .status-badge {{
            display: inline-block;
            padding: 8px 24px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 700;
            color: #fff;
            background: {status_color};
            margin-top: 12px;
        }}
        
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .metric-card {{
            background: #fff;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            text-align: center;
        }}
        .metric-card .value {{
            font-size: 36px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .metric-card .label {{
            font-size: 13px;
            color: #718096;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metric-card.passed .value {{ color: #27ae60; }}
        .metric-card.failed .value {{ color: #e74c3c; }}
        .metric-card.warned .value {{ color: #f39c12; }}
        
        .progress-bar {{
            height: 12px;
            background: #e2e8f0;
            border-radius: 6px;
            overflow: hidden;
            margin: 16px 0;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #48bb78, #38a169);
            border-radius: 6px;
            transition: width 0.3s ease;
        }}
        
        .section {{
            background: #fff;
            border-radius: 10px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
        }}
        .section h2 {{
            font-size: 18px;
            margin-bottom: 16px;
            color: #1a365d;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 8px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            background: #edf2f7;
            color: #4a5568;
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #cbd5e0;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e2e8f0;
        }}
        tr:hover {{ background: #f7fafc; }}
        
        .badge {{
            display: inline-block;
            padding: 3px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge.passed {{ background: #c6f6d5; color: #22543d; }}
        .badge.failed {{ background: #fed7d7; color: #822727; }}
        .badge.warned {{ background: #fefcbf; color: #744210; }}
        .badge.error {{ background: #feb2b2; color: #742a2a; }}
        .badge.skipped {{ background: #e2e8f0; color: #4a5568; }}
        
        .severity-critical {{ border-left: 4px solid #e74c3c; }}
        .severity-high {{ border-left: 4px solid #f39c12; }}
        .severity-medium {{ border-left: 4px solid #3498db; }}
        
        .footer {{
            text-align: center;
            padding: 20px;
            color: #a0aec0;
            font-size: 12px;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 16px;
            margin: 20px 0;
        }}
        .summary-box {{
            background: #f7fafc;
            padding: 16px;
            border-radius: 8px;
            border-left: 4px solid #3182ce;
        }}
        .summary-box h3 {{ font-size: 14px; color: #2d3748; margin-bottom: 8px; }}
        .summary-box .stat {{ font-size: 24px; font-weight: 700; color: #1a365d; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 SEI to Advent Advantage - Comprehensive Test Report</h1>
            <div class="subtitle">Generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}</div>
            <div class="status-badge">{status}</div>
        </div>
        
        <div class="metrics">
            <div class="metric-card">
                <div class="value">{total_tests}</div>
                <div class="label">Total Tests</div>
            </div>
            <div class="metric-card passed">
                <div class="value">{total_passed}</div>
                <div class="label">Passed</div>
            </div>
            <div class="metric-card failed">
                <div class="value">{total_failed}</div>
                <div class="label">Failed</div>
            </div>
            <div class="metric-card warned">
                <div class="value">{total_warned}</div>
                <div class="label">Warned</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Pass Rate: {pass_pct}%</h2>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {pass_pct}%"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; color: #718096;">
                <span>{total_passed} / {total_tests} tests passed</span>
                <span>{pass_pct}%</span>
            </div>
        </div>
        
        <div class="summary-grid">
            <div class="summary-box">
                <h3>Phase 1: dbt Tests</h3>
                <div class="stat">{dbt_summary['passed']} / {dbt_summary['passed'] + dbt_summary['failed'] + dbt_summary.get('errored', 0)}</div>
            </div>
            <div class="summary-box">
                <h3>Phase 2: DuckDB Validations</h3>
                <div class="stat">{db_summary['passed']} / {db_summary['passed'] + db_summary['failed']}</div>
            </div>
            <div class="summary-box">
                <h3>Phase 3: Great Expectations</h3>
                <div class="stat">{gx_summary['passed']} / {gx_summary['passed'] + gx_summary['failed']}</div>
            </div>
        </div>
        
        <div class="section">
            <h2>🧪 Phase 1: dbt Native Tests ({dbt_summary['passed']}/{dbt_summary['passed']+dbt_summary['failed']+dbt_summary.get('errored',0)})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Test Name</th>
                        <th>Category</th>
                        <th>Time (s)</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for test in dbt_results:
        status = test["status"]
        badge_class = {
            "pass": "passed",
            "fail": "failed",
            "warn": "warned",
            "error": "error",
            "skipped": "skipped"
        }.get(status, "error")
        
        html += f"""
                    <tr>
                        <td>{test['name']}</td>
                        <td>{test['category']}</td>
                        <td>{test.get('execution_time', '')}</td>
                        <td><span class="badge {badge_class}">{status}</span></td>
                    </tr>
"""
    
    html += f"""
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>🔬 Phase 2: DuckDB Data Validations ({db_summary['passed']}/{db_summary['passed']+db_summary['failed']})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Check</th>
                        <th>Category</th>
                        <th>Observed</th>
                        <th>Severity</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for test in db_results:
        status = test["status"]
        badge_class = "passed" if status == "passed" else "failed"
        severity = test.get("severity", "medium")
        row_class = f"severity-{severity}" if severity in ["critical", "high"] else ""
        
        html += f"""
                    <tr class="{row_class}">
                        <td>{test['name']}</td>
                        <td>{test.get('category', '')}</td>
                        <td>{test.get('observed', '')}</td>
                        <td><span class="badge {severity}">{severity}</span></td>
                        <td><span class="badge {badge_class}">{status}</span></td>
                    </tr>
"""
    
    html += f"""
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>✅ Phase 3: Great Expectations ({gx_summary['passed']}/{gx_summary['passed']+gx_summary['failed']})</h2>
"""
    
    if gx_results:
        html += """
            <table>
                <thead>
                    <tr>
                        <th>Checkpoint</th>
                        <th>Category</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
        for test in gx_results:
            status = test["status"]
            badge_class = "passed" if status == "passed" else "failed"
            html += f"""
                    <tr>
                        <td>{test['name']}</td>
                        <td>{test.get('category', '')}</td>
                        <td><span class="badge {badge_class}">{status}</span></td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
"""
    else:
        html += "<p>No Great Expectations checks configured or executed.</p>"
    
    html += f"""
        </div>
        
        <div class="footer">
            <p>SEI to Advent Test Automation Suite</p>
            <p>Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>Database: {DB_PATH}</p>
        </div>
    </div>
</body>
</html>
"""
    
    report_path = os.path.join(REPORTS_DIR, f"comprehensive_test_report_{TIMESTAMP}.html")
    latest_path = os.path.join(REPORTS_DIR, "comprehensive_test_report_latest.html")
    
    with open(report_path, "w") as f:
        f.write(html)
    with open(latest_path, "w") as f:
        f.write(html)
    
    print(f"\n  📄 HTML Report: {report_path}")
    return report_path


def generate_json_report(
    dbt_results: List[Dict],
    dbt_summary: Dict,
    db_results: List[Dict],
    db_summary: Dict,
    gx_results: List[Dict],
    gx_summary: Dict
) -> str:
    """Generate JSON report for CI/CD integration."""
    
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "PASSED" if (
            dbt_summary["failed"] + dbt_summary.get("errored", 0) +
            db_summary["failed"] + gx_summary["failed"]
        ) == 0 else "FAILED",
        "summary": {
            "dbt": dbt_summary,
            "duckdb": db_summary,
            "great_expectations": gx_summary,
            "total": {
                "passed": dbt_summary["passed"] + db_summary["passed"] + gx_summary["passed"],
                "failed": (dbt_summary["failed"] + dbt_summary.get("errored", 0) +
                          db_summary["failed"] + gx_summary["failed"]),
                "warned": dbt_summary.get("warned", 0)
            }
        },
        "results": {
            "dbt_tests": dbt_results,
            "duckdb_validations": db_results,
            "great_expectations": gx_results
        }
    }
    
    json_path = os.path.join(REPORTS_DIR, f"test_report_{TIMESTAMP}.json")
    latest_json_path = os.path.join(REPORTS_DIR, "test_report_latest.json")
    
    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2)
    with open(latest_json_path, "w") as f:
        json.dump(report_data, f, indent=2)
    
    print(f"  📄 JSON Report: {json_path}")
    return json_path


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main test execution orchestrator."""
    parser = argparse.ArgumentParser(
        description="Comprehensive Test Suite for SEI to Advent Transformation"
    )
    parser.add_argument(
        "--selector",
        help="dbt test selector (e.g., 'tag:critical')",
        default=None
    )
    parser.add_argument(
        "--skip-dbt",
        action="store_true",
        help="Skip dbt tests"
    )
    parser.add_argument(
        "--skip-duckdb",
        action="store_true",
        help="Skip DuckDB validations"
    )
    parser.add_argument(
        "--skip-gx",
        action="store_true",
        help="Skip Great Expectations"
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("  SEI to Advent Advantage - Comprehensive Test Automation")
    print("=" * 80)
    print(f"  Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Database: {DB_PATH}")
    print("=" * 80)
    
    # Execute test phases
    dbt_results, dbt_summary = ([], {"passed": 0, "failed": 0, "warned": 0, "errored": 0, "skipped": 0}) \
        if args.skip_dbt else run_dbt_tests(args.selector)
    
    db_results, db_summary = ([], {"passed": 0, "failed": 0}) \
        if args.skip_duckdb else run_duckdb_validations()
    
    gx_results, gx_summary = ([], {"passed": 0, "failed": 0}) \
        if args.skip_gx else run_great_expectations()
    
    # Generate reports
    print("\n" + "=" * 80)
    print("  REPORT GENERATION")
    print("=" * 80)
    
    html_report = generate_html_report(
        dbt_results, dbt_summary,
        db_results, db_summary,
        gx_results, gx_summary
    )
    json_report = generate_json_report(
        dbt_results, dbt_summary,
        db_results, db_summary,
        gx_results, gx_summary
    )
    
    # Final summary
    total_failed = (dbt_summary["failed"] + dbt_summary.get("errored", 0) +
                   db_summary["failed"] + gx_summary["failed"])
    total_passed = dbt_summary["passed"] + db_summary["passed"] + gx_summary["passed"]
    
    print("\n" + "=" * 80)
    print(f"  FINAL RESULT: {'✅ PASSED' if total_failed == 0 else '❌ FAILED'}")
    print("=" * 80)
    print(f"  Total Tests: {total_passed + total_failed}")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print(f"  End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Exit with appropriate code
    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
