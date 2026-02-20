# ── Patch 1: DynamicCache fix (transformers >= v4.41) ──
from transformers import cache_utils
if not hasattr(cache_utils.DynamicCache, "get_max_length"):
    cache_utils.DynamicCache.get_max_length = (
        lambda self: self.get_seq_length()
    )

# ── Patch 2: Phi-3.5 attention mask tensor size mismatch fix ──
import transformers.modeling_attn_mask_utils as _attn_utils

_original_prepare = _attn_utils._prepare_4d_causal_attention_mask

def _patched_prepare_4d_causal_attention_mask(
    attention_mask, input_shape, inputs_embeds, past_key_values_length, sliding_window=None
):
    import torch
    seq_len = input_shape[-1]
    if attention_mask is not None and attention_mask.shape[-1] != seq_len:
        attention_mask = attention_mask[:, -seq_len:]
    return _original_prepare(
        attention_mask, input_shape, inputs_embeds,
        past_key_values_length, sliding_window
    )

_attn_utils._prepare_4d_causal_attention_mask = _patched_prepare_4d_causal_attention_mask
# ── End patches ──

"""
PDFExtractor.py — Phi-3.5 Local Model Edition
==============================================
Extracts tables from a PDF, treats each table heading as an Entity,
and uses your LOCAL Phi-3.5 model to generate attribute descriptions.

Features:
  - Handles tables spanning multiple pages (auto-merged)
  - Blackwell GPU optimized (CUDA 13.0 / PyTorch 2.10+)
  - --skip-llm flag for instant extraction without LLM
  - --pages flag to process a subset of pages
  - Outputs JSON + CSV + Excel automatically

Requirements:
  pip install pdfplumber pandas transformers torch accelerate openpyxl bitsandbytes

Usage:
  # Full run
  python PDFExtractor.py --pdf Chapter.pdf

  # Fast run — column names only, no LLM descriptions
  python PDFExtractor.py --pdf Chapter.pdf --skip-llm

  # Test on first 50 pages only
  python PDFExtractor.py --pdf Chapter.pdf --pages 1-50

  # Custom output folder
  python PDFExtractor.py --pdf Chapter.pdf --output C:/SEI/results/entities.json
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import pdfplumber
import pandas as pd

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
DEFAULT_MODEL_PATH = r"C:/sei/aneeshmodel/phi 3 4k instruct"
MAX_NEW_TOKENS     = 256   # reduced from 512 — faster, enough for JSON descriptions
# ──────────────────────────────────────────────

_pipeline = None  # loaded once, reused for all tables


# ══════════════════════════════════════════════
# 1. MODEL LOADING
# ══════════════════════════════════════════════

def load_model(model_path: str):
    """
    Load Phi-3.5 from local directory.
    Optimized for Blackwell RTX Pro 1000 8GB (CUDA 13.0 / PyTorch 2.10).
    """
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    print(f"\n🔄 Loading Phi-3.5 from: {model_path}")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

    if not torch.cuda.is_available():
        print("   ⚠  CUDA not found — running on CPU (will be slow)")

    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
    )

    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="cuda",
            low_cpu_mem_usage=True,
            trust_remote_code=True,
            max_memory={0: "7600MB"},
        )
        precision = "float16"

    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            print("   ⚠  float16 OOM — switching to 4-bit quantization")
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

    # Fix for transformers >= v4.41 DynamicCache breaking change
    try:
        model.generation_config.cache_implementation = None
    except Exception:
        pass

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

    print("   ✅ Phi-3.5 ready\n")
    return _pipeline


def ask_llm(prompt: str, model_path: str) -> str:
    """Call Phi-3.5 directly via model.generate() — bypasses pipeline attention mask bug."""
    pipe = load_model(model_path)
    tokenizer = pipe.tokenizer
    messages = [{"role": "user", "content": prompt}]

    if hasattr(tokenizer, "apply_chat_template"):
        formatted = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        formatted = f"<|user|>\n{prompt}<|end|>\n<|assistant|>\n"

    import torch
    inputs = tokenizer(
        formatted,
        return_tensors="pt",
        padding=False,
        truncation=True,
        max_length=3072,
    ).to(pipe.model.device)

    input_ids      = inputs["input_ids"]
    attention_mask = inputs["attention_mask"]

    # Ensure exact same length — fixes tensor size mismatch
    seq_len        = input_ids.shape[1]
    attention_mask = attention_mask[:, :seq_len]

    with torch.no_grad():
        output_ids = pipe.model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            use_cache=False,    # disables KV cache — avoids all DynamicCache bugs
        )

    new_tokens = output_ids[0][seq_len:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


# ══════════════════════════════════════════════
# 2. PDF HELPERS
# ══════════════════════════════════════════════

def extract_text_lines(page):
    text = page.extract_text() or ""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def get_words_above(page, table_top: float) -> dict:
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
    Returns (True, skip_first_row) if curr_table continues previous table.
    Returns False if it's a new table.

    4 signals must all pass:
      1. Same column count
      2. Table starts in top 35% of page
      3. No substantial new heading above it
      4. Detects repeated header row to skip
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
        is_page_num   = closest_line.replace(" ", "").isdigit()
        is_repeat_hdr = all(
            w.lower() in [c.lower() for c in prev_columns]
            for w in closest_line.split() if w
        )
        if not is_page_num and not is_repeat_hdr and len(closest_line) > 15:
            return False

    # Signal 4: detect repeated header row
    skip_first_row = (
        [c.lower() for c in first_row] == [c.lower() for c in prev_columns]
    )

    return True, skip_first_row


# ══════════════════════════════════════════════
# 4. LLM ENRICHMENT
# ══════════════════════════════════════════════

# Shorter prompt = faster inference on 482-page PDFs
PROMPT_TEMPLATE = """Return ONLY a JSON array for this database table. No markdown, no explanation.
Each element must have exactly: {{"attribute": "columnName", "description": "one sentence"}}

Entity: {entity_name}
Columns: {columns}

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
    print(f" ⚠  JSON parse failed — using raw column names")
    return [{"attribute": c, "description": ""} for c in columns]


def enrich_with_llm(entity_name: str, columns: list, model_path: str) -> list:
    """Note: sample rows removed from prompt — faster inference, still good quality."""
    prompt = PROMPT_TEMPLATE.format(
        entity_name=entity_name,
        columns=" | ".join(columns),
    )
    return parse_llm_json(ask_llm(prompt, model_path), columns, entity_name)


# ══════════════════════════════════════════════
# 5. MAIN PIPELINE
# ══════════════════════════════════════════════

def process_pdf(
    pdf_path: str,
    model_path: str,
    output_json: str,
    skip_llm: bool = False,
    page_range: str = None,
):
    print(f"\n📄 PDF: {pdf_path}")
    start_time = time.time()

    raw_entities = []
    prev_columns = None
    prev_idx     = None

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"   Total pages : {total_pages}")

        # Apply page range if specified
        if page_range:
            try:
                p_start, p_end = map(int, page_range.split("-"))
                pages     = pdf.pages[p_start - 1: p_end]
                page_nums = list(range(p_start, p_end + 1))
                print(f"   Processing  : pages {p_start}–{p_end} only")
            except ValueError:
                print(f"   ⚠  Invalid --pages format '{page_range}', expected e.g. '1-50'")
                pages     = pdf.pages
                page_nums = list(range(1, total_pages + 1))
        else:
            pages     = pdf.pages
            page_nums = list(range(1, total_pages + 1))

        print(f"   Mode        : {'⚡ FAST (skip-llm)' if skip_llm else '🤖 LLM descriptions'}\n")

        for page_num, page in zip(page_nums, pages):
            raw_tables = page.extract_tables()
            if not raw_tables:
                prev_columns = None
                prev_idx     = None
                continue

            text_lines  = extract_text_lines(page)
            page_tables = page.find_tables()

            for idx, (table, pt) in enumerate(zip(raw_tables, page_tables)):
                if not table:
                    continue

                bbox = pt.bbox

                # Check for cross-page continuation
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
                    print(f"  🔗 Page {page_num:>4} | Table {idx+1} → "
                          f"CONTINUATION of '{raw_entities[prev_idx]['entity']}'"
                          f"{' [header skipped]' if skip_first else ''}")
                    continue

                # New table
                raw_heading = find_heading_for_table(page, bbox, text_lines)
                entity_name = to_pascal_case(raw_heading)

                existing = [e["entity"] for e in raw_entities]
                if entity_name in existing:
                    entity_name = f"{entity_name}_P{page_num}T{idx+1}"

                columns, data_rows = parse_table_header(table)

                print(f"  📋 Page {page_num:>4} | Table {idx+1} → '{entity_name}'  "
                      f"[{len(columns)} cols]")

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

    # ── PDF scan complete ──
    scan_time = time.time() - start_time
    print(f"\n✅ PDF scan complete — {len(raw_entities)} entities found "
          f"in {scan_time:.1f}s\n")

    if not raw_entities:
        print("⚠  No tables found in PDF. Check if the PDF has selectable text "
              "(not scanned images).")
        return {}

    # ── LLM enrichment ──
    entities    = {}
    llm_start   = time.time()
    total       = len(raw_entities)

    for i, raw in enumerate(raw_entities, 1):
        name      = raw["entity"]
        page_info = (
            f"page {raw['pages'][0]}"
            if len(raw["pages"]) == 1
            else f"pages {raw['pages'][0]}–{raw['pages'][-1]}"
        )

        if skip_llm:
            # Fast mode — just use column names, no descriptions
            attributes = [{"attribute": c, "description": ""} for c in raw["columns"]]
            print(f"  ⚡ [{i:>3}/{total}] '{name}' ({page_info}) — skipped")
        else:
            t0 = time.time()
            print(f"  🤖 [{i:>3}/{total}] '{name}' ({page_info})...", end="", flush=True)
            attributes = enrich_with_llm(name, raw["columns"], model_path)
            elapsed    = time.time() - t0

            # Estimate remaining time
            avg_time   = (time.time() - llm_start) / i
            remaining  = avg_time * (total - i)
            print(f" ✅ {elapsed:.1f}s  |  ~{remaining/60:.1f} min remaining")

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
    out_path = Path(output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(list(entities.values()), f, indent=2, ensure_ascii=False)
    print(f"\n💾 JSON  → {out_path}")

    # ── CSV ──
    csv_path = out_path.with_suffix(".csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"📄 CSV   → {csv_path}")

    # ── Excel ──
    xlsx_path = out_path.with_suffix(".xlsx")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="All Entities", index=False)
        for ent in entities.values():
            sheet_name = ent["entity"][:31]
            ent_df     = pd.DataFrame(ent["attributes"])
            ent_df.to_excel(writer, sheet_name=sheet_name, index=False)
        for sheet in writer.sheets.values():
            for col in sheet.columns:
                max_len = max(
                    (len(str(cell.value)) for cell in col if cell.value), default=10
                )
                sheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)
    print(f"📊 Excel → {xlsx_path}")

    total_time = time.time() - start_time
    print(f"\n✨ Done — {len(entities)} entities | {len(rows)} attributes | "
          f"Total time: {total_time/60:.1f} min")

    return entities


# ══════════════════════════════════════════════
# 6. CLI
# ══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Extract PDF tables as entities using local Phi-3.5 model",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--pdf", required=True,
        help="Path to input PDF file"
    )
    parser.add_argument(
        "--model-path", default=DEFAULT_MODEL_PATH,
        help=f"Local Phi-3.5 directory\n(default: {DEFAULT_MODEL_PATH})"
    )
    parser.add_argument(
        "--output", default="entities.json",
        help="Base output path — .json .csv .xlsx all generated\n(default: entities.json)"
    )
    parser.add_argument(
        "--skip-llm", action="store_true",
        help="Skip LLM calls — extract column names only (very fast, no descriptions)"
    )
    parser.add_argument(
        "--pages", default=None,
        help="Process only a page range e.g. '1-50' (useful for testing)"
    )
    args = parser.parse_args()

    if not Path(args.pdf).exists():
        print(f"❌ PDF not found: {args.pdf}")
        sys.exit(1)

    if not args.skip_llm and not Path(args.model_path).exists():
        print(f"❌ Model directory not found: {args.model_path}")
        sys.exit(1)

    print("\n" + "="*55)
    print("  PDFExtractor — Phi-3.5 Entity Extractor")
    print("="*55)
    print(f"  PDF        : {args.pdf}")
    print(f"  Model      : {args.model_path}")
    print(f"  Output     : {args.output}")
    print(f"  Skip LLM   : {args.skip_llm}")
    print(f"  Pages      : {args.pages or 'all'}")
    print("="*55)

    process_pdf(
        pdf_path=args.pdf,
        model_path=args.model_path,
        output_json=args.output,
        skip_llm=args.skip_llm,
        page_range=args.pages,
    )


if __name__ == "__main__":
    main()
