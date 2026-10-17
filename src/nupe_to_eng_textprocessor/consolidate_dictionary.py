#!/usr/bin/env python3
"""
Consolidate validated Nupe dictionary page JSON files into one JSONL dataset.

- One output line per DictionaryEntry (all senses remain grouped).
- Does not modify source page JSON files.
- Does not merge repeated headwords or page continuations.
- Preserves the entry fields and adds a stable record_id plus source filename/page metadata.
- Writes a report JSON with counts and any skipped/problematic records.

Example from project root:
    python consolidate_dictionary.py --input-dir output/validated

Defaults:
    input:  output/validated
    output: output/master_dictionary.jsonl
    report: output/consolidation_report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_ENTRY_FIELDS = ("headword", "senses")


def stable_record_id(entry: dict[str, Any], printed_page: Any, pdf_page: Any, ordinal: int) -> str:
    """
    Deterministic ID based on source location and entry content.
    Ordinal disambiguates repeated identical entries on the same source page.
    """
    payload = json.dumps(
        {
            "printed_page": printed_page,
            "pdf_page": pdf_page,
            "ordinal": ordinal,
            "entry": entry,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"nupe-{printed_page or 'unknown'}-{ordinal:03d}-{digest}"


def read_page(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Could not read valid JSON: {exc}"

    if not isinstance(data, dict):
        return None, "Top-level JSON value is not an object."

    if not isinstance(data.get("entries"), list):
        return None, "Missing or invalid 'entries' list."

    return data, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consolidate page-level validated dictionary JSON files into JSONL."
    )
    parser.add_argument("--input-dir", type=Path, default=Path("output/validated"))
    parser.add_argument("--pattern", default="*validated*.json")
    parser.add_argument("--output", type=Path, default=Path("output/master_dictionary.jsonl"))
    parser.add_argument("--report", type=Path, default=Path("output/consolidation_report.json"))
    parser.add_argument(
        "--expected-pages",
        type=int,
        default=204,
        help="Expected number of unique printed pages (default: 204).",
    )
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="Allow replacing an existing output JSONL/report. Otherwise stop if output exists.",
    )
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        print(f"ERROR: input directory not found: {args.input_dir.resolve()}", file=sys.stderr)
        return 2

    files = sorted(
        p for p in args.input_dir.glob(args.pattern)
        if p.is_file()
        and p.resolve() != args.output.resolve()
        and p.resolve() != args.report.resolve()
    )
    if not files:
        print(f"ERROR: no files matched {args.pattern!r} in {args.input_dir.resolve()}", file=sys.stderr)
        return 2

    if not args.allow_overwrite:
        existing = [p for p in (args.output, args.report) if p.exists()]
        if existing:
            print("ERROR: output already exists; refusing to overwrite:", file=sys.stderr)
            for p in existing:
                print(f"  {p.resolve()}", file=sys.stderr)
            print("Choose different --output/--report paths or add --allow-overwrite.", file=sys.stderr)
            return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    # First pass: read files and identify duplicate page numbers before exporting.
    page_items: list[tuple[Path, dict[str, Any], int | None]] = []
    problems: list[dict[str, Any]] = []
    page_files: dict[int, list[str]] = {}
    files_read = 0

    for path in files:
        data, error = read_page(path)
        if error:
            problems.append({"file": str(path), "issue": error})
            continue

        files_read += 1
        page_number = data.get("printed_page_number")
        if not isinstance(page_number, int):
            entries = data["entries"]
            candidates = {
                e.get("source_printed_page")
                for e in entries
                if isinstance(e, dict) and isinstance(e.get("source_printed_page"), int)
            }
            if len(candidates) == 1:
                page_number = candidates.pop()
            else:
                page_number = None

        if page_number is None:
            # Last resort: use page number in the filename. This is reported in the report.
            import re
            match = re.search(r"page[_-]?(\d+)", path.stem, re.IGNORECASE)
            if match:
                page_number = int(match.group(1))
                problems.append({
                    "file": str(path),
                    "issue": f"Printed page number inferred from filename as {page_number}; confirm metadata."
                })

        if isinstance(page_number, int):
            page_files.setdefault(page_number, []).append(path.name)
        page_items.append((path, data, page_number))

    duplicate_pages = {
        page: names for page, names in page_files.items() if len(names) > 1
    }
    if duplicate_pages:
        print("ERROR: multiple input files refer to the same printed page.")
        print("Resolve duplicate page files before consolidation:")
        for page, names in sorted(duplicate_pages.items()):
            print(f"  Page {page}: {', '.join(names)}")
        return 2

    unique_pages = set(page_files)
    expected_pages = set(range(1, args.expected_pages + 1))
    missing_pages = sorted(expected_pages - unique_pages)
    unexpected_pages = sorted(unique_pages - expected_pages)

    if missing_pages or unexpected_pages:
        print("ERROR: input page coverage does not match the expected range.")
        print("Missing pages:", missing_pages or "none")
        print("Unexpected pages:", unexpected_pages or "none")
        print("No master dataset was written. Fix input files or adjust --expected-pages.")
        return 2

    total_entries = 0
    written_entries = 0
    skipped_entries = 0
    entry_issue_counts = Counter()
    output_temp = args.output.with_suffix(args.output.suffix + ".tmp")

    try:
        with output_temp.open("w", encoding="utf-8", newline="\n") as out:
            for path, data, printed_page in sorted(
                page_items,
                key=lambda item: (
                    item[2] if item[2] is not None else 10**9,
                    item[0].name.casefold(),
                ),
            ):
                entries = data["entries"]
                total_entries += len(entries)
                pdf_page = data.get("pdf_page_number")

                for ordinal, entry in enumerate(entries, start=1):
                    if not isinstance(entry, dict):
                        skipped_entries += 1
                        entry_issue_counts["entry_not_object"] += 1
                        problems.append({
                            "file": str(path),
                            "printed_page_number": printed_page,
                            "entry_ordinal": ordinal,
                            "issue": "Entry is not a JSON object; skipped.",
                        })
                        continue

                    missing_fields = [field for field in REQUIRED_ENTRY_FIELDS if field not in entry]
                    if missing_fields:
                        skipped_entries += 1
                        entry_issue_counts["missing_required_fields"] += 1
                        problems.append({
                            "file": str(path),
                            "printed_page_number": printed_page,
                            "entry_ordinal": ordinal,
                            "issue": f"Entry missing fields {missing_fields}; skipped.",
                        })
                        continue

                    record = dict(entry)
                    record["record_id"] = stable_record_id(
                        entry=entry,
                        printed_page=printed_page,
                        pdf_page=pdf_page,
                        ordinal=ordinal,
                    )
                    # Add provenance fields without overwriting any existing entry values.
                    record["source_file"] = path.name
                    if "source_printed_page" not in record and printed_page is not None:
                        record["source_printed_page"] = printed_page
                    if "source_pdf_page" not in record and isinstance(pdf_page, int):
                        record["source_pdf_page"] = pdf_page

                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    written_entries += 1

        # Atomically replace destination only after successful write.
        output_temp.replace(args.output)

    except Exception:
        if output_temp.exists():
            output_temp.unlink()
        raise

    report = {
        "input_directory": str(args.input_dir.resolve()),
        "input_pattern": args.pattern,
        "files_matched": len(files),
        "files_read_successfully": files_read,
        "unique_pages_found": len(unique_pages),
        "expected_pages": args.expected_pages,
        "missing_pages": missing_pages,
        "unexpected_pages": unexpected_pages,
        "duplicate_page_numbers": duplicate_pages,
        "total_entries_in_page_files": total_entries,
        "entries_written": written_entries,
        "entries_skipped": skipped_entries,
        "entry_issue_counts": dict(entry_issue_counts),
        "problems": problems,
        "output_jsonl": str(args.output.resolve()),
    }
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nCONSOLIDATION COMPLETE")
    print("======================")
    print("Input files matched:", len(files))
    print("Files read successfully:", files_read)
    print("Unique pages:", len(unique_pages))
    print("Expected pages:", args.expected_pages)
    print("Entries in page files:", total_entries)
    print("Entries written:", written_entries)
    print("Entries skipped:", skipped_entries)
    print("Warnings/problems recorded:", len(problems))
    print("Master JSONL:", args.output.resolve())
    print("Report JSON:", args.report.resolve())
    if problems:
        print("\nReview the report before treating the master dataset as final.")
    else:
        print("\nNo structural issues were found during consolidation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
