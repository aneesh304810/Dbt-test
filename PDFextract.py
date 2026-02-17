"""
PDF Entity Extractor — Phi-3 Local Model Edition
=================================================
Extracts tables from a PDF, treats each table heading as an Entity,
and uses your LOCAL Phi-3 model to generate attribute descriptions.

KEY FEATURE: Handles tables that span multiple pages — continuation
tables are detected and merged before sending to the LLM.

Requirements:
  pip install pdfplumber pandas transformers torch accelerate openpyxl bitsandbytes

Usage:
  python pdf_entity_extractor.py --pdf your_file.pdf
  python pdf_entity_extractor.py --pdf your_file.pdf --model-path "C:/sei/aneeshmodel/phi 3 4k instruct"
  python pdf_entity_extractor.py --pdf your_file.pdf --output results/entities.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pdfplumber
import pandas as pd

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
DEFAULT_MODEL_PATH = r"C:/sei/aneeshmodel/phi 3 4k instruct"
MAX_NEW_TOKENS     = 512
# ──────────────────────────────────────────────

_pipeline = None  # loaded once, reused


# ══════════════════════════════════════════════
# 1. MODEL LOADING
# ══════════════════════════════════════════════

def load_model(model_path: str):
    """Load Phi-3 from local directory, optimized for RTX 4060 8GB."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    print(f"\n🔄 Loading Phi-3 from: {model_path}")
    print("   Optimized for RTX 4060 8GB (float16, memory-capped)\n")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

    if not torch.cuda.is_available():
        print("   ⚠  CUDA not found — running on CPU (slower)")

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="cuda",
            low_cpu_mem_usage=True,
            trust_remote_code=True,
            max_memory={0: "7600MB"},   # leaves ~400MB headroom on 8GB GPU
        )
        precision = "float16"

    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            print("   ⚠  float16 OOM — switching to 4-bit quantization")
            import torch
            torch.cuda.empty_cache()
            from transformers import BitsAndBytesConfig
            bnb = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                quantization_config=bnb,
                device_map="cuda",
                low_cpu_mem_usage=True,
                trust_remote_code=True,
            )
            precision = "4-bit nf4"
        else:
            raise

    if torch.cuda.is_available():
        vram_used  = torch.cuda.memory_allocated(0) / 1024**3
        vram_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"   GPU  : {torch.cuda.get_device_name(0)}")
        print(f"   VRAM : {vram_used:.1f}GB / {vram_total:.1f}GB  [{precision}]")

    _pipeline = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=MAX_NEW_TOKENS,
        do_sample=False,
        temperature=None,
        top_p=None,
        return_full_text=False,
        pad_token_id=tokenizer.eos_token_id,
    )

    print("   ✅ Phi-3 ready\n")
    return _pipeline


def ask_llm(prompt: str, model_path: str) -> str:
    pipe = load_model(model_path)
    tokenizer = pipe.tokenizer
    messages = [{"role": "user", "content": prompt}]

    if hasattr(tokenizer, "apply_chat_template"):
        formatted = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        formatted = f"<|user|>\n{prompt}<|end|>\n<|assistant|>\n"

    return pipe(formatted)[0]["generated_text"]


# ══════════════════════════════════════════════
# 2. PDF HELPERS
# ══════════════════════════════════════════════

def extract_text_lines(page):
    text = page.extract_text() or ""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def get_words_above(page, table_top: float) -> dict:
    """Return lines of text (as {y_key: [words]}) that appear above table_top."""
    words_above = [
        w for w in (page.extract_words() or [])
        if float(w["bottom"]) <= table_top
    ]
    line_groups = {}
    for w in words_above:
        key = round(float(w["top"]) / 5) * 5
        line_groups.setdefault(key, []).append(w["text"])
    return line_groups


def find_heading_for_table(page, table_bbox, text_lines):
    x0, top, x1, bottom = table_bbox
    line_groups = get_words_above(page, top)

    if line_groups:
        closest_y = max(line_groups.keys())
        return " ".join(line_groups[closest_y]).strip()

    return text_lines[-1] if text_lines else "UnknownEntity"


def to_pascal_case(raw: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", raw)
    return "".join(w.capitalize() for w in words) if words else "Entity"


def parse_table_header(table):
    """Return (columns, data_rows). Detects if first row is a header."""
    first_row = [str(c).strip() if c else "" for c in table[0]]
    is_header = all(
        cell == "" or not cell.replace(".", "").replace("-", "").replace(" ", "").isnumeric()
        for cell in first_row
    )
    if is_header:
        cols = [c if c else f"col_{i}" for i, c in enumerate(first_row)]
        return cols, table[1:]
    return [f"col_{i}" for i in range(len(first_row))], table


# ══════════════════════════════════════════════
# 3. CROSS-PAGE CONTINUATION DETECTION
# ══════════════════════════════════════════════

def check_continuation(prev_columns: list, curr_table: list, curr_page, curr_bbox):
    """
    Determine if curr_table is a continuation of the previous page's table.

    Returns:
        (True, skip_first_row)  — continuation; skip_first_row=True if repeated header
        False                   — new table
    
    Detection logic uses 4 signals:

    Signal 1 — Column count matches previous table
        A continued table always has the same number of columns.

    Signal 2 — Table starts in the top 35% of the page
        When a table overflows to the next page, pdfplumber places it
        near the top (no heading, no gap). A table starting below 35%
        is almost certainly a new section.

    Signal 3 — No substantial new heading above it
        If there IS text above the table, we check whether it's just
        a page number or a repeated column header. If it's a real new
        section heading (>15 chars, not all digits), it's a new table.

    Signal 4 — First row is not a duplicate header
        Some PDFs reprint column headers at the top of each continued
        page. We detect and skip that row when merging.
    """
    if not prev_columns or not curr_table:
        return False

    x0, top, x1, bottom = curr_bbox
    page_height = curr_page.height

    # Signal 1: column count
    first_row = [str(c).strip() if c else "" for c in curr_table[0]]
    if len(first_row) != len(prev_columns):
        return False

    # Signal 2: table near top of page
    if top > page_height * 0.35:
        return False

    # Signal 3: check text above
    line_groups = get_words_above(curr_page, top)
    if line_groups:
        closest_line = " ".join(line_groups[max(line_groups.keys())]).strip()
        is_page_num  = closest_line.replace(" ", "").isdigit()
        is_repeat_hdr = all(
            w.lower() in [c.lower() for c in prev_columns]
            for w in closest_line.split() if w
        )
        if not is_page_num and not is_repeat_hdr and len(closest_line) > 15:
            return False  # real new heading → new entity

    # Signal 4: detect repeated header row
    first_row_lower = [c.lower() for c in first_row]
    prev_cols_lower  = [c.lower() for c in prev_columns]
    skip_first_row   = (first_row_lower == prev_cols_lower)

    return True, skip_first_row


# ══════════════════════════════════════════════
# 4. LLM ENRICHMENT
# ══════════════════════════════════════════════

PROMPT_TEMPLATE = """You are a data modeling expert.
Given a database table extracted from a PDF, return a JSON array describing each attribute.

Rules:
- Respond ONLY with a valid JSON array — no markdown, no explanation, no extra text.
- Each element must have exactly two keys: "attribute" and "description".
- "attribute" should be the column name in camelCase or as-is.
- "description" should be a clear one-sentence explanation of what the field represents.

Entity Name: {entity_name}
Column Names: {columns}
Sample Rows (pipe-delimited, up to 3 rows):
{sample_rows}

JSON array:"""


def parse_llm_json(raw: str, columns: list, entity_name: str) -> list:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        result = json.loads(cleaned)
        if isinstance(result, list) and result:
            return result
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[.*?\]", cleaned, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list) and result:
                return result
        except json.JSONDecodeError:
            pass
    print(f"  ⚠  JSON parse failed for '{entity_name}' — using raw column names.")
    return [{"attribute": c, "description": ""} for c in columns]


def enrich_with_llm(entity_name: str, columns: list, data_rows: list, model_path: str) -> list:
    sample_text = "\n".join(
        " | ".join(str(cell) if cell else "" for cell in row)
        for row in data_rows[:3]
    )
    prompt = PROMPT_TEMPLATE.format(
        entity_name=entity_name,
        columns=" | ".join(columns),
        sample_rows=sample_text or "(no sample data available)",
    )
    return parse_llm_json(ask_llm(prompt, model_path), columns, entity_name)


# ══════════════════════════════════════════════
# 5. MAIN PIPELINE
# ══════════════════════════════════════════════

def process_pdf(pdf_path: str, model_path: str, output_json: str):
    print(f"\n📄 PDF: {pdf_path}")

    # Accumulate raw table data before calling LLM
    # Each entry: {entity, raw_heading, start_page, pages, table_index, columns, all_data_rows}
    raw_entities = []
    prev_columns = None
    prev_idx     = None   # index into raw_entities for the last seen table

    with pdfplumber.open(pdf_path) as pdf:
        print(f"   Total pages: {len(pdf.pages)}\n")

        for page_num, page in enumerate(pdf.pages, start=1):
            raw_tables  = page.extract_tables()
            if not raw_tables:
                # A page with no tables breaks any cross-page continuation
                prev_columns = None
                prev_idx     = None
                continue

            text_lines  = extract_text_lines(page)
            page_tables = page.find_tables()

            for idx, (table, pt) in enumerate(zip(raw_tables, page_tables)):
                if not table:
                    continue

                bbox = pt.bbox

                # ── Check for continuation ──
                cont = (
                    check_continuation(prev_columns, table, page, bbox)
                    if prev_columns is not None and prev_idx is not None
                    else False
                )

                if cont:
                    is_cont, skip_first = cont
                    data_rows = table[1:] if skip_first else table
                    raw_entities[prev_idx]["all_data_rows"].extend(data_rows)
                    raw_entities[prev_idx]["pages"].append(page_num)
                    print(f"  🔗 Page {page_num} | Table {idx+1} → "
                          f"CONTINUATION of '{raw_entities[prev_idx]['entity']}'"
                          f"{' [repeated header skipped]' if skip_first else ''}")
                    # prev_columns / prev_idx stay the same — could continue further
                    continue

                # ── New table ──
                raw_heading = find_heading_for_table(page, bbox, text_lines)
                entity_name = to_pascal_case(raw_heading)

                # Deduplicate name
                existing = [e["entity"] for e in raw_entities]
                if entity_name in existing:
                    entity_name = f"{entity_name}_P{page_num}T{idx+1}"

                columns, data_rows = parse_table_header(table)

                print(f"  📋 Page {page_num} | Table {idx+1} → NEW: '{entity_name}'")
                print(f"     Heading : '{raw_heading}'")
                print(f"     Columns : {columns}")

                raw_entities.append({
                    "entity":        entity_name,
                    "raw_heading":   raw_heading,
                    "start_page":    page_num,
                    "pages":         [page_num],
                    "table_index":   idx + 1,
                    "columns":       columns,
                    "all_data_rows": list(data_rows),
                })

                prev_columns = columns
                prev_idx     = len(raw_entities) - 1

    # ── LLM enrichment (after all pages processed & tables merged) ──
    entities = {}
    for raw in raw_entities:
        name = raw["entity"]
        page_info = (
            f"page {raw['pages'][0]}"
            if len(raw["pages"]) == 1
            else f"pages {raw['pages'][0]}–{raw['pages'][-1]} (merged)"
        )
        print(f"\n  🤖 Enriching '{name}' ({page_info}, "
              f"{len(raw['all_data_rows'])} data rows)...")

        attributes = enrich_with_llm(name, raw["columns"], raw["all_data_rows"], model_path)

        entities[name] = {
            "entity":      name,
            "raw_heading": raw["raw_heading"],
            "pages":       raw["pages"],
            "table_index": raw["table_index"],
            "attributes":  attributes,
        }

    # ── Build output DataFrame ──
    rows = []
    for ent in entities.values():
        page_label = (
            str(ent["pages"][0])
            if len(ent["pages"]) == 1
            else f"{ent['pages'][0]}-{ent['pages'][-1]}"
        )
        for attr in ent["attributes"]:
            rows.append({
                "Entity":      ent["entity"],
                "Raw Heading": ent["raw_heading"],
                "Pages":       page_label,
                "Attribute":   attr.get("attribute", ""),
                "Description": attr.get("description", ""),
            })
    df = pd.DataFrame(rows)

    # ── JSON ──
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(list(entities.values()), f, indent=2, ensure_ascii=False)
    print(f"\n💾 JSON  → {output_json}")

    # ── CSV ──
    csv_path = Path(output_json).with_suffix(".csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"📄 CSV   → {csv_path}")

    # ── Excel (flat sheet + one tab per entity) ──
    xlsx_path = Path(output_json).with_suffix(".xlsx")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="All Entities", index=False)
        for ent in entities.values():
            sheet_name = ent["entity"][:31]
            ent_df = pd.DataFrame(ent["attributes"])
            ent_df.to_excel(writer, sheet_name=sheet_name, index=False)
        for sheet in writer.sheets.values():
            for col in sheet.columns:
                max_len = max(
                    (len(str(cell.value)) for cell in col if cell.value), default=10
                )
                sheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)
    print(f"📊 Excel → {xlsx_path}")

    print(f"\n✨ Done — {len(entities)} entities extracted.")
    return entities


# ══════════════════════════════════════════════
# 6. CLI
# ══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Extract PDF tables as entities using local Phi-3 (handles multi-page tables)"
    )
    parser.add_argument("--pdf",        required=True,             help="Path to input PDF")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH, help="Local Phi-3 directory")
    parser.add_argument("--output",     default="entities.json",   help="Base output path (.json/.csv/.xlsx auto-generated)")
    args = parser.parse_args()

    if not Path(args.pdf).exists():
        print(f"❌ PDF not found: {args.pdf}")
        sys.exit(1)
    if not Path(args.model_path).exists():
        print(f"❌ Model directory not found: {args.model_path}")
        sys.exit(1)

    process_pdf(
        pdf_path=args.pdf,
        model_path=args.model_path,
        output_json=args.output,
    )


if __name__ == "__main__":
    main()
