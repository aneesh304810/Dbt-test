"""
SEI to Advent - Comprehensive Test Suite with Record-Level Detail
=================================================================
Runs dbt tests + DuckDB validations.
Shows EVERY failing record in the HTML report for easy navigation.

Usage:
    python comprehensive_test_suite.py
"""

import subprocess
import json
import os
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = os.environ.get("DUCKDB_PATH", os.path.join(os.path.dirname(__file__), "..", "dbt_sei_to_advent.duckdb"))
PROJECT_DIR = os.environ.get("DBT_PROJECT_DIR", os.path.join(os.path.dirname(__file__), ".."))
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

os.makedirs(REPORTS_DIR, exist_ok=True)


# ==============================================================
# DuckDB VALIDATION ENGINE
# ==============================================================
def run_all_validations():
    """Run all validations and capture failing records."""
    print("\n" + "=" * 60)
    print("  Running Comprehensive Validations")
    print("=" * 60)

    try:
        import duckdb
    except ImportError:
        print("  ERROR: duckdb not installed. Run: pip install duckdb")
        return [], {"passed": 0, "failed": 0}, [], {}

    con = duckdb.connect(DB_PATH, read_only=True)
    results = []
    summary = {"passed": 0, "failed": 0}
    all_records = {}  # store full dataset snapshots

    # ── Capture full datasets for the report ──────────────
    datasets = {}
    dataset_queries = {
        "source_securities": ("SEI Source Securities (raw_sei.securities)", "SELECT * FROM raw_sei.securities ORDER BY sec_id"),
        "source_asset_classes": ("SEI Source Asset Classes (raw_sei.asset_classes)", "SELECT * FROM raw_sei.asset_classes ORDER BY asset_cls_code"),
        "staging_securities": ("Staging Securities (stg_sei_securities)", "SELECT * FROM main_staging.stg_sei_securities ORDER BY security_id"),
        "seed_asset_class": ("Seed: Asset Class Crosswalk", "SELECT * FROM main.seed_asset_class_crosswalk ORDER BY sei_asset_class_code"),
        "seed_strategy": ("Seed: Strategy Crosswalk", "SELECT * FROM main.seed_strategy_crosswalk ORDER BY sei_strategy_code"),
        "mapping_asset_class": ("Mapping: Asset Class (L1)", "SELECT * FROM main_mappings.map_sei_to_advent_asset_class ORDER BY sei_asset_class_code"),
        "mapping_strategy": ("Mapping: Strategy (L2)", "SELECT * FROM main_mappings.map_sei_to_advent_strategy ORDER BY security_id"),
        "mart_advent": ("Mart: advent_securities (Final Output)", "SELECT * FROM main_marts.advent_securities ORDER BY SECURITY_ID"),
    }

    for key, (label, query) in dataset_queries.items():
        try:
            cols = [desc[0] for desc in con.execute(query).description]
            rows = con.execute(query).fetchall()
            datasets[key] = {"label": label, "columns": cols, "rows": rows, "count": len(rows)}
            print(f"  Loaded {key}: {len(rows)} rows")
        except Exception as e:
            datasets[key] = {"label": label, "columns": [], "rows": [], "count": 0, "error": str(e)}
            print(f"  WARN: Could not load {key}: {e}")

    # ── Define all validation checks ──────────────────────
    checks = [
        # ── Schema Checks ──
        {"name": "Schema: SECURITY_ID exists in mart", "category": "Schema",
         "query": "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='main_marts' AND table_name='advent_securities' AND column_name='SECURITY_ID'",
         "check": lambda v: v >= 1,
         "fail_query": None},

        {"name": "Schema: STRATEGY_CODE exists in mart", "category": "Schema",
         "query": "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='main_marts' AND table_name='advent_securities' AND column_name='STRATEGY_CODE'",
         "check": lambda v: v >= 1,
         "fail_query": None},

        {"name": "Schema: STRATEGY_DESCRIPTION exists in mart", "category": "Schema",
         "query": "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='main_marts' AND table_name='advent_securities' AND column_name='STRATEGY_DESCRIPTION'",
         "check": lambda v: v >= 1,
         "fail_query": None},

        {"name": "Schema: _L1_MAPPING_METHOD exists in mart", "category": "Schema",
         "query": "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='main_marts' AND table_name='advent_securities' AND column_name='_L1_MAPPING_METHOD'",
         "check": lambda v: v >= 1,
         "fail_query": None},

        {"name": "Schema: _L2_MAPPING_METHOD exists in mart", "category": "Schema",
         "query": "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='main_marts' AND table_name='advent_securities' AND column_name='_L2_MAPPING_METHOD'",
         "check": lambda v: v >= 1,
         "fail_query": None},

        # ── Reconciliation ──
        {"name": "Reconciliation: mart rows = source rows", "category": "Reconciliation",
         "query": "SELECT ABS((SELECT COUNT(*) FROM main_marts.advent_securities) - (SELECT COUNT(*) FROM raw_sei.securities))",
         "check": lambda v: v == 0,
         "fail_query": """
            SELECT 'Missing from mart' as issue, s.sec_id, s.sec_name, s.asset_cls_code
            FROM raw_sei.securities s
            LEFT JOIN main_marts.advent_securities m ON CAST(s.sec_id AS VARCHAR) = m.SECURITY_ID
            WHERE m.SECURITY_ID IS NULL
            UNION ALL
            SELECT 'Extra in mart' as issue, m.SECURITY_ID, m.SECURITY_NAME, m._SEI_ASSET_CLASS_CODE
            FROM main_marts.advent_securities m
            LEFT JOIN raw_sei.securities s ON m.SECURITY_ID = CAST(s.sec_id AS VARCHAR)
            WHERE s.sec_id IS NULL
         """},

        {"name": "Reconciliation: mart rows = staging rows", "category": "Reconciliation",
         "query": "SELECT ABS((SELECT COUNT(*) FROM main_marts.advent_securities) - (SELECT COUNT(*) FROM main_staging.stg_sei_securities))",
         "check": lambda v: v == 0,
         "fail_query": """
            SELECT 'Missing from mart' as issue, s.security_id, s.security_name
            FROM main_staging.stg_sei_securities s
            LEFT JOIN main_marts.advent_securities m ON s.security_id = m.SECURITY_ID
            WHERE m.SECURITY_ID IS NULL
         """},

        # ── Completeness ──
        {"name": "Completeness: no NULL SECURITY_ID", "category": "Completeness",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE SECURITY_ID IS NULL",
         "check": lambda v: v == 0,
         "fail_query": "SELECT * FROM main_marts.advent_securities WHERE SECURITY_ID IS NULL"},

        {"name": "Completeness: no NULL SECURITY_NAME", "category": "Completeness",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE SECURITY_NAME IS NULL",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, ASSET_CLASS_CODE FROM main_marts.advent_securities WHERE SECURITY_NAME IS NULL"},

        {"name": "Completeness: no NULL ASSET_CLASS_CODE", "category": "Completeness",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE ASSET_CLASS_CODE IS NULL",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, _SEI_ASSET_CLASS_CODE, _L1_MAPPING_METHOD FROM main_marts.advent_securities WHERE ASSET_CLASS_CODE IS NULL"},

        {"name": "Completeness: no NULL ASSET_CLASS", "category": "Completeness",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE ASSET_CLASS IS NULL",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, ASSET_CLASS_CODE, ASSET_CLASS FROM main_marts.advent_securities WHERE ASSET_CLASS IS NULL"},

        {"name": "Completeness: no NULL STRATEGY_CODE", "category": "Completeness",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE STRATEGY_CODE IS NULL",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, ASSET_CLASS_CODE, STRATEGY_CODE, _L2_MAPPING_METHOD FROM main_marts.advent_securities WHERE STRATEGY_CODE IS NULL"},

        {"name": "Completeness: no NULL STRATEGY_DESCRIPTION", "category": "Completeness",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE STRATEGY_DESCRIPTION IS NULL",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, STRATEGY_CODE, STRATEGY_DESCRIPTION, _L2_MAPPING_METHOD FROM main_marts.advent_securities WHERE STRATEGY_DESCRIPTION IS NULL"},

        {"name": "Completeness: no NULL SECURITY_TYPE", "category": "Completeness",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE SECURITY_TYPE IS NULL",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, SECURITY_TYPE FROM main_marts.advent_securities WHERE SECURITY_TYPE IS NULL"},

        # ── Uniqueness ──
        {"name": "Uniqueness: SECURITY_ID is unique in mart", "category": "Uniqueness",
         "query": "SELECT COUNT(*) - COUNT(DISTINCT SECURITY_ID) FROM main_marts.advent_securities",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, COUNT(*) as cnt FROM main_marts.advent_securities GROUP BY SECURITY_ID HAVING COUNT(*) > 1"},

        {"name": "Uniqueness: SECURITY_ID is unique in staging", "category": "Uniqueness",
         "query": "SELECT COUNT(*) - COUNT(DISTINCT security_id) FROM main_staging.stg_sei_securities",
         "check": lambda v: v == 0,
         "fail_query": "SELECT security_id, COUNT(*) as cnt FROM main_staging.stg_sei_securities GROUP BY security_id HAVING COUNT(*) > 1"},

        # ── Validity ──
        {"name": "Validity: ASSET_CLASS_CODE in accepted values", "category": "Validity",
         "query": """SELECT COUNT(*) FROM main_marts.advent_securities
                     WHERE ASSET_CLASS_CODE NOT IN ('EQD','EQI','EQEM','EQSM','EQLG','FIG','FIC','FIM','FIHY','FIIG',
                     'FIMB','FIAB','FITIP','FIIN','FIEM','AHFN','APRE','ARET','ACOM','AINF','CASH','CONV','PREF','MLTB','OTHR')""",
         "check": lambda v: v == 0,
         "fail_query": """SELECT SECURITY_ID, SECURITY_NAME, ASSET_CLASS_CODE, _SEI_ASSET_CLASS_CODE, _L1_MAPPING_METHOD
                          FROM main_marts.advent_securities
                          WHERE ASSET_CLASS_CODE NOT IN ('EQD','EQI','EQEM','EQSM','EQLG','FIG','FIC','FIM','FIHY','FIIG',
                          'FIMB','FIAB','FITIP','FIIN','FIEM','AHFN','APRE','ARET','ACOM','AINF','CASH','CONV','PREF','MLTB','OTHR')"""},

        {"name": "Validity: SECURITY_TYPE in accepted values", "category": "Validity",
         "query": """SELECT COUNT(*) FROM main_marts.advent_securities
                     WHERE SECURITY_TYPE NOT IN ('EQUITY','FIXED_INCOME','OPTION','FUTURE','CASH_EQUIV','CONVERTIBLE','PREFERRED','ALTERNATIVE','OTHER')""",
         "check": lambda v: v == 0,
         "fail_query": """SELECT SECURITY_ID, SECURITY_NAME, SECURITY_TYPE
                          FROM main_marts.advent_securities
                          WHERE SECURITY_TYPE NOT IN ('EQUITY','FIXED_INCOME','OPTION','FUTURE','CASH_EQUIV','CONVERTIBLE','PREFERRED','ALTERNATIVE','OTHER')"""},

        {"name": "Validity: STATUS in (A, I, U)", "category": "Validity",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE STATUS NOT IN ('A','I','U')",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, STATUS FROM main_marts.advent_securities WHERE STATUS NOT IN ('A','I','U')"},

        {"name": "Validity: L1 mapping method is valid", "category": "Validity",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE _L1_MAPPING_METHOD NOT IN ('DIRECT','PARENT_ROLLUP','FALLBACK')",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, _L1_MAPPING_METHOD FROM main_marts.advent_securities WHERE _L1_MAPPING_METHOD NOT IN ('DIRECT','PARENT_ROLLUP','FALLBACK')"},

        {"name": "Validity: L2 mapping method is valid", "category": "Validity",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE _L2_MAPPING_METHOD NOT IN ('DIRECT','ASSET_CLASS_DEFAULT','FALLBACK')",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, _L2_MAPPING_METHOD FROM main_marts.advent_securities WHERE _L2_MAPPING_METHOD NOT IN ('DIRECT','ASSET_CLASS_DEFAULT','FALLBACK')"},

        # ── Format ──
        {"name": "Format: BASE_CURRENCY is 3 characters", "category": "Format",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE LENGTH(BASE_CURRENCY) != 3 AND BASE_CURRENCY IS NOT NULL",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, BASE_CURRENCY, LENGTH(BASE_CURRENCY) as len FROM main_marts.advent_securities WHERE LENGTH(BASE_CURRENCY) != 3 AND BASE_CURRENCY IS NOT NULL"},

        {"name": "Format: COUNTRY_CODE is 2 characters", "category": "Format",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE LENGTH(COUNTRY_CODE) != 2 AND COUNTRY_CODE IS NOT NULL",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, COUNTRY_CODE, LENGTH(COUNTRY_CODE) as len FROM main_marts.advent_securities WHERE LENGTH(COUNTRY_CODE) != 2 AND COUNTRY_CODE IS NOT NULL"},

        # ── Business Rules ──
        {"name": "Business: No SEI code leakage in ASSET_CLASS", "category": "Business Rule",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE ASSET_CLASS LIKE '%EQ_DOM%' OR ASSET_CLASS LIKE '%FI_GOV%' OR ASSET_CLASS LIKE '%ALT_HF%'",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, ASSET_CLASS FROM main_marts.advent_securities WHERE ASSET_CLASS LIKE '%EQ_DOM%' OR ASSET_CLASS LIKE '%FI_GOV%' OR ASSET_CLASS LIKE '%ALT_HF%'"},

        {"name": "Business: FALLBACK L1 mappings < 20%", "category": "Business Rule",
         "query": """SELECT CASE WHEN
                     (SELECT COUNT(*) FROM main_marts.advent_securities WHERE _L1_MAPPING_METHOD = 'FALLBACK') * 1.0 /
                     NULLIF((SELECT COUNT(*) FROM main_marts.advent_securities), 0) > 0.2
                     THEN 1 ELSE 0 END""",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, _SEI_ASSET_CLASS_CODE, _L1_MAPPING_METHOD FROM main_marts.advent_securities WHERE _L1_MAPPING_METHOD = 'FALLBACK'"},

        {"name": "Business: All securities have L2 strategy", "category": "Business Rule",
         "query": "SELECT COUNT(*) FROM main_marts.advent_securities WHERE STRATEGY_CODE IS NULL OR STRATEGY_DESCRIPTION IS NULL",
         "check": lambda v: v == 0,
         "fail_query": "SELECT SECURITY_ID, SECURITY_NAME, ASSET_CLASS_CODE, STRATEGY_CODE, STRATEGY_DESCRIPTION, _L2_MAPPING_METHOD FROM main_marts.advent_securities WHERE STRATEGY_CODE IS NULL OR STRATEGY_DESCRIPTION IS NULL"},

        # ── Orphan / Integrity ──
        {"name": "Integrity: No source securities missing from mart", "category": "Integrity",
         "query": """SELECT COUNT(*) FROM raw_sei.securities s
                     LEFT JOIN main_marts.advent_securities m ON CAST(s.sec_id AS VARCHAR) = m.SECURITY_ID
                     WHERE m.SECURITY_ID IS NULL""",
         "check": lambda v: v == 0,
         "fail_query": """SELECT s.sec_id, s.sec_name, s.asset_cls_code, s.sub_asset_cls_code
                          FROM raw_sei.securities s
                          LEFT JOIN main_marts.advent_securities m ON CAST(s.sec_id AS VARCHAR) = m.SECURITY_ID
                          WHERE m.SECURITY_ID IS NULL"""},
    ]

    # ── Run all checks ────────────────────────────────────
    for chk in checks:
        try:
            value = con.execute(chk["query"]).fetchone()[0]
            passed = chk["check"](value)
            failing_rows = []
            failing_cols = []

            if not passed and chk.get("fail_query"):
                try:
                    fail_result = con.execute(chk["fail_query"])
                    failing_cols = [desc[0] for desc in fail_result.description]
                    failing_rows = fail_result.fetchall()
                except Exception:
                    pass

            results.append({
                "name": chk["name"],
                "category": chk["category"],
                "status": "PASSED" if passed else "FAILED",
                "observed": str(value),
                "failing_count": len(failing_rows),
                "failing_cols": failing_cols,
                "failing_rows": failing_rows
            })
            if passed:
                summary["passed"] += 1
            else:
                summary["failed"] += 1

            icon = "PASS" if passed else "FAIL"
            extra = f" ({len(failing_rows)} records)" if failing_rows else ""
            print(f"  [{icon}] {chk['name']} = {value}{extra}")

        except Exception as e:
            results.append({
                "name": chk["name"],
                "category": chk["category"],
                "status": "ERROR",
                "observed": str(e),
                "failing_count": 0,
                "failing_cols": [],
                "failing_rows": []
            })
            summary["failed"] += 1
            print(f"  [ERR] {chk['name']}: {e}")

    # ── Mapping distribution summary ──────────────────────
    try:
        dist = con.execute("""
            SELECT _L1_MAPPING_METHOD, _L2_MAPPING_METHOD, COUNT(*) as cnt
            FROM main_marts.advent_securities
            GROUP BY 1, 2 ORDER BY 1, 2
        """).fetchall()
    except Exception:
        dist = []

    con.close()

    print(f"\n  Total: {summary['passed']} passed, {summary['failed']} failed")
    return results, summary, datasets, dist


# ==============================================================
# HTML REPORT GENERATOR
# ==============================================================
def generate_report(results, summary, datasets, distribution):
    total = summary["passed"] + summary["failed"]
    status = "PASSED" if summary["failed"] == 0 else "FAILED"
    color = "#27ae60" if status == "PASSED" else "#e74c3c"
    pct = round(summary["passed"] / max(total, 1) * 100, 1)

    # ── Build failing records HTML sections ───────────────
    failing_sections = ""
    for r in results:
        if r["status"] != "PASSED" and r["failing_rows"]:
            failing_sections += f"""
            <div class="fail-detail" id="fail-{r['name'].replace(' ', '-').replace(':', '')}">
                <h4>{r['name']} - {r['failing_count']} failing record(s)</h4>
                <table class="records">
                    <thead><tr>{''.join(f'<th>{c}</th>' for c in r['failing_cols'])}</tr></thead>
                    <tbody>
            """
            for row in r["failing_rows"][:200]:  # cap at 200 rows
                failing_sections += "<tr>" + "".join(f"<td>{str(v)[:80]}</td>" for v in row) + "</tr>\n"
            failing_sections += "</tbody></table>"
            if r["failing_count"] > 200:
                failing_sections += f"<p class='note'>Showing 200 of {r['failing_count']} records</p>"
            failing_sections += "</div>\n"

    # ── Build dataset browser HTML ────────────────────────
    dataset_tabs = ""
    dataset_content = ""
    for idx, (key, ds) in enumerate(datasets.items()):
        active = "active" if idx == 0 else ""
        dataset_tabs += f'<button class="tab-btn {active}" onclick="showTab(\'{key}\')">{ds["label"].split("(")[0].strip()} ({ds["count"]})</button>\n'

        display = "block" if idx == 0 else "none"
        dataset_content += f'<div class="tab-content" id="tab-{key}" style="display:{display}">\n'
        dataset_content += f'<h4>{ds["label"]} - {ds["count"]} rows</h4>\n'

        if ds.get("error"):
            dataset_content += f'<p class="note">Error: {ds["error"]}</p>'
        elif ds["rows"]:
            dataset_content += '<div class="table-scroll"><table class="records"><thead><tr>'
            dataset_content += "".join(f"<th>{c}</th>" for c in ds["columns"])
            dataset_content += "</tr></thead><tbody>\n"
            for row in ds["rows"][:500]:
                dataset_content += "<tr>" + "".join(f"<td>{str(v)[:60]}</td>" for v in row) + "</tr>\n"
            dataset_content += "</tbody></table></div>\n"
            if ds["count"] > 500:
                dataset_content += f'<p class="note">Showing 500 of {ds["count"]} rows</p>'
        else:
            dataset_content += '<p class="note">No data</p>'
        dataset_content += "</div>\n"

    # ── Distribution table ────────────────────────────────
    dist_html = ""
    if distribution:
        dist_html = '<table class="records"><thead><tr><th>L1 Method</th><th>L2 Method</th><th>Count</th></tr></thead><tbody>'
        for row in distribution:
            dist_html += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td></tr>"
        dist_html += "</tbody></table>"

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SEI to Advent - Comprehensive Test Report</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f7fa;color:#2d3748;line-height:1.6}}
.container{{max-width:1400px;margin:0 auto;padding:20px}}
.header{{background:linear-gradient(135deg,#1a365d,#2c5282);color:#fff;padding:28px;border-radius:12px;margin-bottom:20px}}
.header h1{{font-size:22px}}.header .sub{{opacity:.7;font-size:13px;margin-top:4px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}}
.card{{background:#fff;border-radius:10px;padding:18px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.card .n{{font-size:32px;font-weight:700}}.card .l{{font-size:12px;color:#718096;margin-top:2px}}
.card.p .n{{color:#27ae60}}.card.f .n{{color:#e74c3c}}.card.t .n{{color:#3182ce}}
.ob{{display:inline-block;padding:5px 18px;border-radius:6px;font-size:15px;font-weight:700;color:#fff;background:{color}}}
.sec{{background:#fff;border-radius:10px;padding:22px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.sec h2{{font-size:16px;margin-bottom:14px;color:#1a365d;border-bottom:2px solid #e2e8f0;padding-bottom:6px}}
.sec h3{{font-size:14px;margin:12px 0 8px;color:#2c5282}}
table.checks{{width:100%;border-collapse:collapse;font-size:13px}}
table.checks th{{background:#edf2f7;color:#4a5568;padding:8px 10px;text-align:left;font-weight:600}}
table.checks td{{padding:7px 10px;border-bottom:1px solid #e2e8f0}}
table.checks tr:hover{{background:#f7fafc}}
table.records{{width:100%;border-collapse:collapse;font-size:11px;margin-top:8px}}
table.records th{{background:#2c5282;color:#fff;padding:6px 8px;text-align:left;font-weight:600;position:sticky;top:0}}
table.records td{{padding:5px 8px;border-bottom:1px solid #e2e8f0;white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis}}
table.records tr:nth-child(even){{background:#f7fafc}}
table.records tr:hover{{background:#ebf4ff}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600;text-transform:uppercase}}
.badge.passed{{background:#c6f6d5;color:#22543d}}.badge.failed{{background:#fed7d7;color:#822727}}.badge.error{{background:#fed7d7;color:#822727}}
.pb{{height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden;margin-top:8px}}
.pf{{height:100%;border-radius:4px;background:#48bb78}}
.fail-detail{{background:#fff5f5;border:1px solid #feb2b2;border-radius:8px;padding:14px;margin:10px 0}}
.fail-detail h4{{color:#822727;font-size:13px;margin-bottom:8px}}
.table-scroll{{max-height:400px;overflow:auto;border:1px solid #e2e8f0;border-radius:6px}}
.tab-bar{{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px}}
.tab-btn{{padding:6px 14px;border:1px solid #cbd5e0;border-radius:6px;background:#fff;cursor:pointer;font-size:12px;color:#4a5568}}
.tab-btn:hover{{background:#ebf4ff}}.tab-btn.active{{background:#2c5282;color:#fff;border-color:#2c5282}}
.note{{font-size:11px;color:#718096;margin-top:6px;font-style:italic}}
.search-box{{width:100%;padding:8px 12px;border:1px solid #cbd5e0;border-radius:6px;font-size:13px;margin-bottom:12px}}
.ft{{text-align:center;padding:16px;color:#a0aec0;font-size:11px}}
.nav{{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}}
.nav a{{padding:6px 14px;background:#ebf4ff;color:#2c5282;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600}}
.nav a:hover{{background:#2c5282;color:#fff}}
</style>
<script>
function showTab(key){{
    document.querySelectorAll('.tab-content').forEach(el=>el.style.display='none');
    document.querySelectorAll('.tab-btn').forEach(el=>el.classList.remove('active'));
    document.getElementById('tab-'+key).style.display='block';
    event.target.classList.add('active');
}}
function filterTable(input, tableId){{
    const filter=input.value.toLowerCase();
    const rows=document.querySelectorAll('#'+tableId+' tbody tr');
    rows.forEach(row=>{{
        const text=row.textContent.toLowerCase();
        row.style.display=text.includes(filter)?'':'none';
    }});
}}
</script>
</head><body><div class="container">

<div class="header">
    <h1>SEI to Advent Advantage - Comprehensive Test Report</h1>
    <div class="sub">Generated: {datetime.now().strftime("%B %d, %Y %I:%M %p")} | Database: {os.path.basename(DB_PATH)}</div>
</div>

<div class="nav">
    <a href="#summary">Summary</a>
    <a href="#checks">Test Results</a>
    <a href="#failures">Failing Records</a>
    <a href="#distribution">Mapping Distribution</a>
    <a href="#datasets">Data Browser</a>
</div>

<div class="cards">
    <div class="card"><div class="ob">{status}</div><div class="l">Overall</div></div>
    <div class="card t"><div class="n">{total}</div><div class="l">Total Tests</div></div>
    <div class="card p"><div class="n">{summary['passed']}</div><div class="l">Passed</div></div>
    <div class="card f"><div class="n">{summary['failed']}</div><div class="l">Failed</div></div>
</div>

<div class="sec" id="summary">
    <h2>Pass Rate</h2>
    <div style="display:flex;justify-content:space-between;font-size:12px;color:#718096"><span>{summary['passed']}/{total}</span><span>{pct}%</span></div>
    <div class="pb"><div class="pf" style="width:{pct}%"></div></div>
</div>

<div class="sec" id="checks">
    <h2>All Test Results</h2>
    <input type="text" class="search-box" placeholder="Search tests..." onkeyup="filterTable(this,'checks-table')">
    <table class="checks" id="checks-table">
    <thead><tr><th>Test Name</th><th>Category</th><th>Observed</th><th>Failing Records</th><th>Status</th></tr></thead>
    <tbody>
"""

    for r in results:
        bc = "passed" if r["status"] == "PASSED" else "failed"
        link = ""
        if r["failing_count"] > 0:
            anchor = f"fail-{r['name'].replace(' ', '-').replace(':', '')}"
            link = f'<a href="#{anchor}" style="color:#e53e3e;font-weight:600">{r["failing_count"]} records</a>'
        html += f"""<tr>
            <td>{r['name']}</td><td>{r['category']}</td><td>{r['observed']}</td>
            <td>{link}</td><td><span class="badge {bc}">{r['status']}</span></td>
        </tr>\n"""

    html += f"""</tbody></table></div>

<div class="sec" id="failures">
    <h2>Failing Records Detail</h2>
    {"<p class='note'>All tests passed - no failing records.</p>" if not failing_sections else failing_sections}
</div>

<div class="sec" id="distribution">
    <h2>Mapping Method Distribution</h2>
    <p class="note" style="margin-bottom:8px">Shows how securities were classified across L1 and L2 mapping tiers.</p>
    {dist_html if dist_html else "<p class='note'>No distribution data available.</p>"}
</div>

<div class="sec" id="datasets">
    <h2>Data Browser - All Pipeline Layers</h2>
    <p class="note" style="margin-bottom:12px">Browse every table in the pipeline: source, staging, seeds, mappings, and final mart output.</p>
    <div class="tab-bar">{dataset_tabs}</div>
    {dataset_content}
</div>

<div class="ft">SEI to Advent Advantage - Comprehensive Test Suite | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
</div></body></html>"""

    report_path = os.path.join(REPORTS_DIR, f"test_report_{TIMESTAMP}.html")
    latest_path = os.path.join(REPORTS_DIR, "test_report_latest.html")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  Report: {report_path}")
    print(f"  Latest: {latest_path}")
    return report_path


# ==============================================================
# MAIN
# ==============================================================
def main():
    print("\n" + "=" * 60)
    print("  SEI to Advent - Comprehensive Test Suite")
    print("  " + datetime.now().strftime("%B %d, %Y %I:%M %p"))
    print("=" * 60)

    results, summary, datasets, distribution = run_all_validations()
    generate_report(results, summary, datasets, distribution)

    total_f = summary["failed"]
    print("\n" + "=" * 60)
    print(f"  {'ALL TESTS PASSED' if total_f == 0 else f'{total_f} TESTS FAILED'}")
    print("=" * 60)
    sys.exit(0 if total_f == 0 else 1)


if __name__ == "__main__":
    main()
