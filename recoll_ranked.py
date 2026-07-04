#!/usr/bin/env python3
"""
Recoll Index + Search + PyMuPDF Context Extractor
-------------------------------------------------
- Lets user specify directories to index via --index
- Optionally runs full reindex with --full
- Performs Recoll search (--query)
- Uses PyMuPDF to extract top passages centered around query hits
"""

import subprocess
import argparse
import sys
import math
import re
from pathlib import Path
from urllib.parse import urlparse, unquote
import fitz  # PyMuPDF


# =======================
# CONFIG
# =======================
RECOLLQ = "/Applications/Recoll.app/Contents/MacOS/recollq"
RECOLLINDEX = "/Applications/Recoll.app/Contents/MacOS/recollindex"

BASE_DIR = Path.home() / ".my_recoll_tool"
CONF_DIR = BASE_DIR / "recoll"
CONF_FILE = CONF_DIR / "recoll.conf"


# =======================
# INDEXING
# =======================
def write_recoll_conf(directories):
    """
    Create or overwrite Recoll configuration with the chosen directories.
    """
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    dirs = " ".join(str(Path(d).expanduser().resolve()) for d in directories)
    content = [
        f"topdirs = {dirs}",
        "indexStoreText = 1",
        "idxabsmlen = 5000",
        "useAspell = 0",
    ]
    CONF_FILE.write_text("\n".join(content) + "\n", encoding="utf-8")
    print(f"[INFO] Created recoll.conf at: {CONF_FILE}")


def run_indexer(full=False):
    """
    Run recollindex on the configured directories.
    """
    cmd = [RECOLLINDEX, "-c", str(CONF_DIR)]
    if full:
        cmd.append("-z")  # Full rebuild
    print(f"[INFO] Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    if result.returncode != 0:
        print("[ERROR] recollindex failed:\n", result.stderr)
        sys.exit(1)

    print("[INFO] Indexing completed successfully.\n")


# =======================
# RECOLL SEARCH
# =======================
def run_recoll(query, top_docs):
    cmd = [
        RECOLLQ,
        "-c", str(CONF_DIR),
        "-n", str(top_docs),
        query
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        print("Recoll search failed:\n", result.stderr)
        sys.exit(1)

    ranked_paths = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or "\t" not in line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue

        file_field = parts[1].strip()
        if not file_field.startswith("[file://"):
            continue

        file_url = file_field.strip("[]")
        path = unquote(urlparse(file_url).path)
        if path.lower().endswith(".pdf"):
            ranked_paths.append(path)

    return ranked_paths


# =======================
# QUERY TOKENIZATION
# =======================
def parse_query(query: str):
    query = query.strip().lower()

    if " " in query:
        return {"type": "phrase", "phrase": query, "terms": query.split()}
    return {"type": "term", "terms": [query]}


# =======================
# PAGE SCORING
# =======================
def looks_like_index_or_toc(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return True
    short_lines = sum(1 for l in lines if len(l) < 40)
    if short_lines / len(lines) > 0.6:
        return True
    comma_ratio = sum(l.count(",") for l in lines) / max(len(lines), 1)
    if comma_ratio > 1.5:
        return True
    alpha_headers = sum(1 for l in lines if len(l) == 1 and l.isalpha())
    if alpha_headers >= 3:
        return True
    return False


def score_page(text, query_info):
    text_l = text.lower()
    if looks_like_index_or_toc(text):
        return 0.0
    score = 0.0
    if query_info["type"] == "phrase":
        phrase = query_info["phrase"]
        if phrase not in text_l:
            return 0.0
        score += 50
        score += text_l.count(phrase) * 20
    hits = sum(1 for t in query_info["terms"] if t in text_l)
    if hits == 0:
        return 0.0
    length = max(len(text_l), 1)
    density = hits / length
    sentences = text_l.count(".") + text_l.count(";")
    score += hits * 5
    score += density * 1000
    score += sentences * 0.2
    return score


def position_penalty(page_num, total_pages):
    if page_num < total_pages * 0.05:
        return 0.7
    if page_num > total_pages * 0.9:
        return 0.3
    return 1.0


def rank_pages(pdf_path, query_info):
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    scored = []
    for i, page in enumerate(doc):
        text = page.get_text()
        base_score = score_page(text, query_info)
        if base_score <= 0:
            continue
        penalty = position_penalty(i, total_pages)
        final_score = base_score * penalty
        if final_score > 0:
            scored.append((final_score, i, text))
    scored.sort(reverse=True)
    return scored


# =======================
# HIT-CENTERED CONTEXT
# =======================
def extract_hit_context(text, query_info, word_radius=150):
    text_l = text.lower()
    if query_info["type"] == "phrase":
        phrase = query_info["phrase"].lower()
        match = re.search(re.escape(phrase), text_l)
        if not match:
            return None
        start_idx, end_idx = match.span()
        hit_text = text[start_idx:end_idx]
    else:
        hit_text = None
        for term in query_info["terms"]:
            m = re.search(re.escape(term), text_l)
            if m:
                start_idx, end_idx = m.span()
                hit_text = text[start_idx:end_idx]
                break
        if not hit_text:
            return None

    words = re.findall(r"\w+|\W+", text)
    tokens_only = [w for w in words if re.match(r"\w+", w)]
    hit_words = re.findall(r"\w+", hit_text)
    if not hit_words:
        return None
    first_hit = hit_words[0].lower()
    word_positions = [i for i, w in enumerate(tokens_only) if w.lower() == first_hit]
    if not word_positions:
        return None
    hit_pos = word_positions[0]
    start_word = max(0, hit_pos - word_radius)
    end_word = min(len(tokens_only), hit_pos + len(hit_words) + word_radius)
    context_words = tokens_only[start_word:end_word]
    return " ".join(context_words).strip()


# =======================
# PIPELINE
# =======================
def retrieve_ranked_passages(query, top_docs, top_passages, word_radius):
    query_info = parse_query(query)
    ranked_docs = run_recoll(query, top_docs)
    results = []
    for doc_rank, pdf_path in enumerate(ranked_docs, start=1):
        try:
            page_scores = rank_pages(pdf_path, query_info)
        except Exception as e:
            print(f"[WARN] Could not read {pdf_path}: {e}")
            continue
        for page_score, page_num, text in page_scores[:top_passages]:
            context = extract_hit_context(text, query_info, word_radius)
            if not context:
                continue
            results.append({
                "doc_rank": doc_rank,
                "pdf": pdf_path,
                "page": page_num + 1,
                "page_score": page_score,
                "context": context
            })
    return results


# =======================
# OUTPUT
# =======================
def write_output(results, out_path):
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {Path(r['pdf']).name}")
        lines.append(f"   Document rank: {r['doc_rank']}")
        lines.append(f"   Page: {r['page']}  (page score={r['page_score']:.2f})")
        lines.append("")
        lines.append(r["context"])
        lines.append("\n" + "-" * 80 + "\n")
    out_path.write_text("\n".join(lines), encoding="utf-8")


# =======================
# CLI
# =======================
def main():
    parser = argparse.ArgumentParser(description="Recoll + PyMuPDF Ranked Passage Retrieval with Indexing")

    parser.add_argument("--index", nargs="+", help="Directories to index before searching")
    parser.add_argument("--full", action="store_true", help="Force full reindex (-z)")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--top-docs", type=int, default=5, help="Top Y documents from Recoll")
    parser.add_argument("--top-passages", type=int, default=3, help="Top X passages per document")
    parser.add_argument("--word_radius", type=int, default=500, help="Words before/after keyword")
    parser.add_argument("--out", type=Path, default=Path("../ranked_results.txt"), help="Output file")

    args = parser.parse_args()

    # Handle indexing if user specified directories
    if args.index:
        write_recoll_conf(args.index)
        run_indexer(full=args.full)

    results = retrieve_ranked_passages(
        query=args.query,
        top_docs=args.top_docs,
        top_passages=args.top_passages,
        word_radius=args.word_radius
    )

    write_output(results, args.out)
    print(f"\n[INFO] Results written to: {args.out.resolve()}")


if __name__ == "__main__":
    main()
