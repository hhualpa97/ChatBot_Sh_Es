#!/usr/bin/env python3
"""
Batch HTML → TXT converter (Python stdlib only).

Features:
- Safe HTML parsing (no regex) to extract readable plain text.
- Preserves basic structure: paragraphs, headings, lists, line breaks, simple tables.
- Skips non‑content tags: script, style, noscript.
- Decodes entities and normalizes whitespace.

Options:
- Drop content of specific tags (default: sup, sub) via `--drop-tags`.
- Strip standalone angle‑bracket arrow tokens (e.g., "<", ">", "<<", ">>") via `--strip-angle-buttons`.
- Remove verse‑like leading numbers at line start via `--strip-leading-numbers`.
- Output modes: per‑file TXT (default), merge to single file (`--single-file`), or single‑only (`--single-only`).
- Extensions are configurable via `--ext` (default: htm,html).

Usage examples:
  # Write per-file TXT under outputs/processed/<name>_txt/
  python3 scripts/convert/html_to_txt.py -i Corpus/shpNTpo_html --dest-scope outputs

  # Add URL annotations after link text
  python3 scripts/convert/html_to_txt.py -i Corpus/shpNTpo_html --include-urls

  # Recurse into subdirectories
  python3 scripts/convert/html_to_txt.py -i Corpus/shpNTpo_html --recursive

  # Convert and also write a single concatenated TXT
  python3 scripts/convert/html_to_txt.py -i Corpus/shpNTpo_html \
    --single-file outputs/processed/shpNTpo_txt/all.txt

  # Produce ONLY the single concatenated TXT (no per-file outputs)
  python3 scripts/convert/html_to_txt.py -i Corpus/shpNTpo_html \
    --single-only --strip-leading-numbers
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import List, Optional


BLOCK_TAGS = {
    "p",
    "div",
    "section",
    "article",
    "header",
    "footer",
    "address",
    "aside",
    "blockquote",
}

HEADING_TAGS = {f"h{i}" for i in range(1, 7)}
LIST_CONTAINER_TAGS = {"ul", "ol"}
LIST_ITEM_TAG = "li"
TABLE_ROW_TAG = "tr"
TABLE_CELL_TAGS = {"td", "th"}
SKIP_TAGS = {"script", "style", "noscript"}

# Standalone tokens that often represent nav "buttons" to strip if requested
ANGLE_ARROW_TOKENS = {"<", ">", "<<", ">>", "<>", "«", "»", "‹", "›", "◀", "▶", "▲", "▼"}


def _collapse_spaces(s: str) -> str:
    # Collapse runs of whitespace to single spaces
    return re.sub(r"\s+", " ", s)


@dataclass
class AnchorCtx:
    href: Optional[str] = None
    text_start_index: int = 0  # buffer length index when <a> starts


class TextExtractor(HTMLParser):
    def __init__(self, include_urls: bool = False, drop_tags: Optional[List[str]] = None, strip_angle_buttons: bool = False):
        super().__init__(convert_charrefs=True)
        self.include_urls = include_urls
        self.buf: List[str] = []
        self.skip_depth = 0
        self.drop_depth = 0
        self.in_pre = False
        self.list_level = 0
        self.cell_index = 0
        self.anchor_stack: List[AnchorCtx] = []
        self.drop_tags = {t.lower() for t in (drop_tags or [])}
        self.strip_angle_buttons = strip_angle_buttons

    # ---- helpers ----
    def _last_char(self) -> str:
        if not self.buf:
            return ""
        last = self.buf[-1]
        return last[-1] if last else ""

    def _append(self, text: str):
        if not text:
            return
        self.buf.append(text)

    def _space_if_needed(self):
        if self._last_char() not in ("", " ", "\n", "\t"):
            self.buf.append(" ")

    def _ensure_newlines(self, n: int = 1):
        # Ensure at least n trailing newlines
        cur = 0
        i = len(self.buf) - 1
        while i >= 0 and cur < n:
            chunk = self.buf[i]
            j = len(chunk) - 1
            while j >= 0 and cur < n and chunk[j] == "\n":
                cur += 1
                j -= 1
            if cur >= n:
                break
            if j >= 0:
                break
            i -= 1
        if cur < n:
            self.buf.append("\n" * (n - cur))

    def _paragraph_break(self):
        # Separate blocks with a blank line
        self._ensure_newlines(2)

    # ---- parser callbacks ----
    def handle_starttag(self, tag: str, attrs):
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return

        if self.skip_depth > 0:
            return

        if tag in self.drop_tags:
            self.drop_depth += 1
            return

        if tag == "br":
            self._ensure_newlines(1)
            return

        if tag in BLOCK_TAGS or tag in HEADING_TAGS:
            self._paragraph_break()

        if tag in LIST_CONTAINER_TAGS:
            self.list_level += 1
            self._paragraph_break()
            return

        if tag == LIST_ITEM_TAG:
            self._ensure_newlines(1)
            indent = "  " * max(0, self.list_level - 1)
            self._append(f"{indent}• ")
            return

        if tag == TABLE_ROW_TAG:
            self._ensure_newlines(1)
            self.cell_index = 0
            return

        if tag in TABLE_CELL_TAGS:
            if self.cell_index > 0:
                self._append("\t")
            self.cell_index += 1
            return

        if tag == "pre":
            self._paragraph_break()
            self.in_pre = True
            return

        if tag == "a":
            href = None
            for k, v in attrs:
                if k.lower() == "href":
                    href = v
                    break
            self.anchor_stack.append(AnchorCtx(href=href, text_start_index=len(self.buf)))
            return

    def handle_endtag(self, tag: str):
        if tag in SKIP_TAGS:
            if self.skip_depth > 0:
                self.skip_depth -= 1
            return

        if self.skip_depth > 0:
            return

        if tag in self.drop_tags:
            if self.drop_depth > 0:
                self.drop_depth -= 1
            return

        if tag in BLOCK_TAGS or tag in HEADING_TAGS:
            self._paragraph_break()
            return

        if tag in LIST_CONTAINER_TAGS:
            self.list_level = max(0, self.list_level - 1)
            self._paragraph_break()
            return

        if tag == LIST_ITEM_TAG:
            self._ensure_newlines(1)
            return

        if tag == TABLE_ROW_TAG:
            self._ensure_newlines(1)
            self.cell_index = 0
            return

        if tag in TABLE_CELL_TAGS:
            # nothing; tabs added at start
            return

        if tag == "pre":
            self.in_pre = False
            self._paragraph_break()
            return

        if tag == "a":
            if not self.anchor_stack:
                return
            ctx = self.anchor_stack.pop()
            if self.include_urls and ctx.href:
                # Check if anchor has visible text
                anchor_text = "".join(self.buf[ctx.text_start_index:]).strip()
                if anchor_text:
                    self._append(f" ({ctx.href})")
            return

    def handle_data(self, data: str):
        if self.skip_depth > 0 or self.drop_depth > 0:
            return

        if not data:
            return

        if self.in_pre:
            # Keep as-is
            self._append(data)
            return

        # Normalize spaces for regular text nodes
        text = _collapse_spaces(data)
        text = text.replace("\xa0", " ")

        # Avoid leading space at start of line
        if self._last_char() in ("", "\n"):
            text = text.lstrip()

        if text:
            # Ensure separation from previous word if needed
            if self._last_char() not in ("", "\n", " ", "\t") and not text.startswith(" "):
                self.buf.append(" ")
            self._append(text)

    def get_text(self) -> str:
        out = "".join(self.buf)
        out = unescape(out)
        # Normalize lines: trim trailing spaces and collapse multiple blank lines
        lines = [re.sub(r"[ \t]+$", "", ln) for ln in out.splitlines()]
        # Collapse 3+ blank lines to a single blank line
        cleaned: List[str] = []
        blank = 0
        for ln in lines:
            if ln.strip():
                cleaned.append(ln)
                blank = 0
            else:
                if blank == 0:
                    cleaned.append("")
                blank = 1
        text = "\n".join(cleaned).strip()

        if self.strip_angle_buttons:
            # Remove standalone angle/arrow tokens that act like nav buttons
            def strip_arrows_line(ln: str) -> str:
                # Replace tokens consisting only of angle/arrow glyphs when separated by whitespace
                def repl(m):
                    token = m.group(0).strip()
                    return "" if token in ANGLE_ARROW_TOKENS else token

                # Surround with spaces to simplify boundary matching
                s = f" {ln} "
                # Replace multiple times to catch adjacent tokens
                prev = None
                while prev != s:
                    prev = s
                    s = re.sub(r"(?<=\s)([«»‹›◀▶▲▼]|[<>]{1,3}|<>) (?=\s)", repl, s)
                    # Collapse any excessive spaces that may result
                    s = re.sub(r"\s+", " ", s)
                return s.strip()

            text = "\n".join(strip_arrows_line(ln) for ln in text.splitlines())

        return text + "\n"


def html_to_text(html: str, include_urls: bool = False, drop_tags: Optional[List[str]] = None, strip_angle_buttons: bool = False) -> str:
    parser = TextExtractor(include_urls=include_urls, drop_tags=drop_tags, strip_angle_buttons=strip_angle_buttons)
    parser.feed(html)
    parser.close()
    return parser.get_text()


def strip_leading_numbers(text: str) -> str:
    """Remove verse-like leading numbers at the start of lines.

    Examples:
      "32 ¿Pregunta?" -> "¿Pregunta?"
      "3. Texto" -> "Texto"

    Only strips when a 1–4 digit number (optionally followed by '.' or ')')
    appears at line start and is followed by spaces then a typical sentence
    starter (letter, quote or Spanish inverted punctuation).
    """
    pat = re.compile(r"^\s*\d{1,4}(?:[.)])?(?=\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ¿¡\"“”'])")
    out_lines: List[str] = []
    for ln in text.splitlines():
        ln2 = pat.sub("", ln, count=1)
        ln2 = re.sub(r"^\s+", "", ln2)
        out_lines.append(ln2)
    return "\n".join(out_lines) + "\n"


def discover_files(root: str, exts: List[str], recursive: bool) -> List[str]:
    exts_norm = tuple(e.lower() if e.startswith(".") else f".{e.lower()}" for e in exts)
    found: List[str] = []
    if recursive:
        for base, _, files in os.walk(root):
            for fn in files:
                if fn.lower().endswith(exts_norm):
                    found.append(os.path.join(base, fn))
    else:
        for fn in os.listdir(root):
            p = os.path.join(root, fn)
            if os.path.isfile(p) and fn.lower().endswith(exts_norm):
                found.append(p)
    return sorted(found)


def collect_txt_files(root: str) -> List[str]:
    """Collect all .txt files under root, sorted by relative path."""
    txts: List[str] = []
    for base, _, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith(".txt"):
                txts.append(os.path.join(base, fn))
    # sort by relative path for stable ordering
    txts.sort(key=lambda p: os.path.relpath(p, root))
    return txts


def merge_txt_files(src_root: str, dest_file: str, include_headers: bool = True, strip_numbers: bool = False):
    files = collect_txt_files(src_root)
    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
    with open(dest_file, "w", encoding="utf-8") as out:
        for i, fp in enumerate(files):
            rel = os.path.relpath(fp, src_root)
            if include_headers:
                out.write(f"===== {rel} =====\n")
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                chunk = f.read()
                if strip_numbers:
                    chunk = strip_leading_numbers(chunk)
                out.write(chunk.rstrip("\n") + "\n")
            if i != len(files) - 1:
                out.write("\n")


def process_to_single(
    input_dir: str,
    dest_file: str,
    include_urls: bool,
    drop_tags: List[str],
    strip_angle_buttons: bool,
    encoding: str,
    recursive: bool,
    exts: List[str],
    include_headers: bool = True,
    strip_numbers: bool = False,
):
    files = discover_files(input_dir, exts, recursive)
    if not files:
        print("No HTML files found.")
        return 0
    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
    processed = 0
    with open(dest_file, "w", encoding="utf-8") as out:
        for i, src in enumerate(files):
            rel = os.path.relpath(src, input_dir)
            if include_headers:
                out.write(f"===== {rel} =====\n")
            try:
                with open(src, "r", encoding=encoding, errors="replace") as f:
                    html = f.read()
                text = html_to_text(
                    html,
                    include_urls=include_urls,
                    drop_tags=drop_tags,
                    strip_angle_buttons=strip_angle_buttons,
                )
                if strip_numbers:
                    text = strip_leading_numbers(text)
                out.write(text.rstrip("\n") + "\n")
                if i != len(files) - 1:
                    out.write("\n")
                processed += 1
            except Exception as e:
                print(f"Error processing {src}: {e}", file=sys.stderr)
    return processed


def _find_repo_root(start: Path) -> Optional[Path]:
    """Best-effort to locate repo root (directory containing .git or outputs/)."""
    cur = start.resolve()
    for _ in range(6):  # up to 6 levels up
        if (cur / ".git").exists() or (cur / "outputs").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _compute_outputs_dir(input_dir: Path) -> Path:
    repo = _find_repo_root(input_dir)
    # Fallback to input parent if repo not found
    root = repo if repo is not None else input_dir.parent
    base = input_dir.name
    name = (base[:-5] + "_txt") if base.endswith("_html") else (base + "_txt")
    return (root / "outputs" / "processed" / name).resolve()


def compute_default_output_dir(input_dir: str, dest_scope: str = "outputs") -> str:
    """Default output location.

    - outputs: <repo>/outputs/processed/<name>_txt (preferred)
    - sibling: <input_dir>/../<name>_txt (legacy behavior)
    """
    in_dir = Path(input_dir).resolve()
    if dest_scope == "outputs":
        return str(_compute_outputs_dir(in_dir))
    # legacy sibling behavior
    base = in_dir.name
    parent = in_dir.parent
    if base.endswith("_html"):
        return str((parent / (base[:-5] + "_txt")).resolve())
    return str((in_dir / "txt_output").resolve())


def process_all(
    input_dir: str,
    output_dir: str,
    include_urls: bool,
    drop_tags: List[str],
    strip_angle_buttons: bool,
    encoding: str,
    recursive: bool,
    exts: List[str],
    strip_numbers: bool = False,
) -> int:
    files = discover_files(input_dir, exts, recursive)
    if not files:
        print("No HTML files found.")
        return 0

    processed = 0
    for src in files:
        rel = os.path.relpath(src, input_dir)
        rel_noext = os.path.splitext(rel)[0]
        dst = os.path.join(output_dir, rel_noext + ".txt")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            with open(src, "r", encoding=encoding, errors="replace") as f:
                html = f.read()
            text = html_to_text(html, include_urls=include_urls, drop_tags=drop_tags, strip_angle_buttons=strip_angle_buttons)
            if strip_numbers:
                text = strip_leading_numbers(text)
            with open(dst, "w", encoding="utf-8", errors="replace") as f:
                f.write(text)
            processed += 1
        except Exception as e:
            print(f"Error processing {src}: {e}", file=sys.stderr)
    return processed


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Convert HTML files to plain text.")
    p.add_argument(
        "-i",
        "--input-dir",
        default=".",
        help="Directory containing .htm/.html files (default: current)",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        default=None,
        help=(
            "Directory to write .txt files. If omitted, writes under "
            "<repo>/outputs/processed/<name>_txt unless --dest-scope sibling is set."
        ),
    )
    p.add_argument(
        "--include-urls",
        action="store_true",
        help="Append (URL) after link text",
    )
    p.add_argument(
        "--drop-tags",
        default="sup,sub",
        help="Comma-separated tag names whose content is dropped (default: sup,sub)",
    )
    p.add_argument(
        "--strip-angle-buttons",
        action="store_true",
        help="Remove standalone < > style arrow tokens often used as nav buttons",
    )
    p.add_argument(
        "--encoding",
        default="utf-8",
        help="Source HTML encoding (default: utf-8)",
    )
    p.add_argument(
        "--ext",
        default="htm,html",
        help="Comma-separated list of extensions to include (default: htm,html)",
    )
    p.add_argument(
        "--recursive",
        action="store_true",
        help="Recurse into subdirectories (default: off)",
    )
    p.add_argument(
        "--dest-scope",
        choices=["outputs", "sibling"],
        default="outputs",
        help=(
            "Default destination if -o/--output-dir is not provided: "
            "'outputs' → <repo>/outputs/processed/<name>_txt, "
            "'sibling' → ../<name>_txt (legacy)."
        ),
    )
    p.add_argument(
        "--strip-leading-numbers",
        action="store_true",
        help="Strip verse-like numbers at the start of lines during conversion",
    )
    p.add_argument(
        "--merge-only",
        action="store_true",
        help="Skip conversion and only merge existing TXT under output_dir",
    )
    p.add_argument(
        "--single-only",
        action="store_true",
        help=(
            "Do not create per-file .txt; convert and write a single output "
            "file (requires --single-file, otherwise defaults to <output_dir>/all.txt)"
        ),
    )
    p.add_argument(
        "--merge-strip-leading-numbers",
        action="store_true",
        help="Also strip leading numbers when creating the single merged file",
    )
    p.add_argument(
        "--single-file",
        default=None,
        help=(
            "Path to write a single concatenated TXT after conversion. "
            "Example: outputs/processed/shpNTpo_txt/all.txt"
        ),
    )
    p.add_argument(
        "--no-section-headers",
        action="store_true",
        help="Do not insert '===== <file> =====' headers in the merged file",
    )

    args = p.parse_args(argv)
    input_dir = os.path.abspath(args.input_dir)
    output_dir = (
        os.path.abspath(args.output_dir)
        if args.output_dir
        else compute_default_output_dir(input_dir, args.dest_scope)
    )
    exts = [e.strip() for e in args.ext.split(",") if e.strip()]
    drop_tags = [t.strip().lower() for t in args.drop_tags.split(",") if t.strip()]

    os.makedirs(output_dir, exist_ok=True)

    count = 0
    if args.single_only:
        single_path = args.single_file or os.path.join(output_dir, "all.txt")
        count = process_to_single(
            input_dir=input_dir,
            dest_file=os.path.abspath(single_path),
            include_urls=args.include_urls,
            drop_tags=drop_tags,
            strip_angle_buttons=args.strip_angle_buttons,
            encoding=args.encoding,
            recursive=args.recursive,
            exts=exts,
            include_headers=not args.no_section_headers,
            strip_numbers=args.strip_leading_numbers,
        )
        print(f"Converted {count} file(s) → {os.path.abspath(single_path)}")
    else:
        if not args.merge_only:
            count = process_all(
                input_dir=input_dir,
                output_dir=output_dir,
                include_urls=args.include_urls,
                drop_tags=drop_tags,
                strip_angle_buttons=args.strip_angle_buttons,
                encoding=args.encoding,
                recursive=args.recursive,
                exts=exts,
                strip_numbers=args.strip_leading_numbers,
            )
            print(f"Converted {count} file(s) → {output_dir}")

        if args.single_file:
            merge_txt_files(
                output_dir,
                os.path.abspath(args.single_file),
                include_headers=not args.no_section_headers,
                strip_numbers=args.merge_strip_leading_numbers or args.strip_leading_numbers,
            )
            print(f"Merged → {os.path.abspath(args.single_file)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
