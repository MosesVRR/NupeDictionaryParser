#!/usr/bin/env python3
"""
Read-only audit of page-level Nupe dictionary JSON files.

Checks:
- Expected page files are present
- JSON parses and validates against DictionaryPage (when the project model imports)
- Page metadata matches the filename where it can be determined
- Entry counts and review-flag counts
- Empty pages and duplicate headwords within a page
- Creates a CSV report and prints a concise summary

Run from the project root, for example:
    python audit_dictionary_pages.py --folder output/validated --expected-pages 204

This script does not modify source JSON files.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PAGE_RE = re.compile(r"page[_-]?(\d+)", re.IGNORECASE)


def load_dictionary_page_model():
    """Try the project's current Pydantic model; return None if unavailable."""
    try:
        from nupe_to_eng_textprocessor.models import DictionaryPage
        return DictionaryPage, None
    except Exception as exc:
        return None, f"Could not import DictionaryPage model: {exc}"


def get_page_number(data: dict[str, Any], path: Path) -> int | None:
    for key in ("printed_page_number", "page_number"):
        value = data.get(key)
        if isinstance(value, int):
            return value

    entries = data.get("entries")
    if isinstance(entries, list):
        values = {
            e.get("source_printed_page")
            for e in entries
            if isinstance(e, dict) and isinstance(e.get("source_printed_page"), int)
        }
        if len(values) == 1:
            return values.pop()

    match = PAGE_RE.search(path.stem)
    return int(match.group(1)) if match else None


def validate_with_model(model, data):
    if model is None:
        return True, "Pydantic model not available; JSON-only validation"
    try:
        model.model_validate(data)
        return True, ""
    except Exception as exc:
        return False, str(exc).replace("\n", " ")[:500]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit extracted dictionary page JSON files.")
    parser.add_argument("--folder", type=Path, default=Path("output/pages"))
    parser.add_argument("--pattern", default="*validated*.json",
                        help="Glob for validated page JSON files (default: *validated*.json)")
    parser.add_argument("--expected-pages", type=int, default=204,
                        help="Expected printed pages (default: 204)")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--report", type=Path, default=Path("output/audit_report.csv"))
    args = parser.parse_args()

    if not args.folder.is_dir():
        print(f"ERROR: folder does not exist: {args.folder.resolve()}", file=sys.stderr)
        print("Use --folder to point to the directory containing the validated JSON files.")
        return 2

    model, model_warning = load_dictionary_page_model()
    if model_warning:
        print("WARNING:", model_warning)
        print("The audit will still check JSON syntax and basic structure.")

    files = sorted(p for p in args.folder.glob(args.pattern) if p.is_file())
    if not files:
        print(f"No files matched {args.pattern!r} in {args.folder.resolve()}")
        print("Check the folder and filename pattern.")
        return 2

    rows = []
    found_page_to_files: dict[int, list[str]] = {}
    errors = Counter()
    total_entries = 0

    for path in files:
        row: dict[str, Any] = {
            "file": str(path),
            "page_number": "",
            "entry_count": "",
            "page_notes_count": "",
            "json_valid": False,
            "schema_valid": False,
            "metadata_matches_filename": "",
            "empty_page": "",
            "duplicate_headwords": "",
            "review_required_true": "",
            "human_verified_true": "",
            "issues": "",
        }
        issues: list[str] = []
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            row["json_valid"] = True
            if not isinstance(data, dict):
                issues.append("top-level JSON is not an object")
                data = {}

            page_num = get_page_number(data, path)
            row["page_number"] = page_num if page_num is not None else ""
            if page_num is not None:
                found_page_to_files.setdefault(page_num, []).append(path.name)

            entries = data.get("entries", [])
            if not isinstance(entries, list):
                issues.append("'entries' is not a list")
                entries = []

            notes = data.get("page_notes", [])
            row["page_notes_count"] = len(notes) if isinstance(notes, list) else ""
            row["entry_count"] = len(entries)
            total_entries += len(entries)
            row["empty_page"] = len(entries) == 0
            if not entries:
                issues.append("zero entries")

            model_ok, model_error = validate_with_model(model, data)
            row["schema_valid"] = model_ok
            if not model_ok:
                issues.append("Pydantic validation failed: " + model_error)

            match = PAGE_RE.search(path.stem)
            if match and page_num is not None:
                filename_page = int(match.group(1))
                row["metadata_matches_filename"] = filename_page == page_num
                if filename_page != page_num:
                    issues.append(f"filename page {filename_page} != metadata page {page_num}")

            headwords = [
                e.get("headword", "").strip().casefold()
                for e in entries if isinstance(e, dict) and isinstance(e.get("headword"), str)
            ]
            counts = Counter(headwords)
            duplicates = sorted(word for word, count in counts.items() if word and count > 1)
            row["duplicate_headwords"] = "; ".join(duplicates)
            if duplicates:
                issues.append("duplicate headwords on same page (review; may be legitimate)")

            row["review_required_true"] = sum(
                1 for e in entries if isinstance(e, dict) and e.get("review_required") is True
            )
            row["human_verified_true"] = sum(
                1 for e in entries if isinstance(e, dict) and e.get("human_verified") is True
            )

        except (OSError, json.JSONDecodeError) as exc:
            issues.append(f"cannot read/parse JSON: {exc}")
            errors["invalid_json"] += 1

        row["issues"] = " | ".join(issues)
        if issues:
            errors["files_with_issues"] += 1
        rows.append(row)

    expected = set(range(args.start_page, args.start_page + args.expected_pages))
    found = set(found_page_to_files)
    missing = sorted(expected - found)
    unexpected = sorted(found - expected)
    duplicate_page_numbers = {
        page: names for page, names in found_page_to_files.items() if len(names) > 1
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "file", "page_number", "entry_count", "page_notes_count", "json_valid",
        "schema_valid", "metadata_matches_filename", "empty_page", "duplicate_headwords",
        "review_required_true", "human_verified_true", "issues"
    ]
    with args.report.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print("\nDICTIONARY PAGE AUDIT")
    print("=====================")
    print("Folder:", args.folder.resolve())
    print("Files matched:", len(files))
    print("Total entries counted:", total_entries)
    print("Pages found:", len(found))
    print("Expected page range:", f"{args.start_page}-{args.start_page + args.expected_pages - 1}")
    print("Missing pages:", ", ".join(map(str, missing)) if missing else "none")
    print("Unexpected page numbers:", ", ".join(map(str, unexpected)) if unexpected else "none")
    print("Duplicate page numbers:", duplicate_page_numbers if duplicate_page_numbers else "none")
    print("Files with issues:", errors["files_with_issues"])
    print("Invalid JSON files:", errors["invalid_json"])
    print("CSV report:", args.report.resolve())

    if errors["files_with_issues"]:
        print("\nFiles to inspect:")
        for row in rows:
            if row["issues"]:
                print(f"- {row['file']} [page {row['page_number']}]: {row['issues']}")

    print("\nNote: duplicate headwords are warnings, not automatic errors; separate entries can legitimately share a headword.")
    print("This audit does not establish transcription accuracy. It checks structure and consistency only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
