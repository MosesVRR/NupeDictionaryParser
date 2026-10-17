#!/usr/bin/env python3
"""
Update review flags in page-level Nupe dictionary JSON files.

By default this script performs a DRY RUN. Add --apply to write changes.
It creates a backup of each file before modifying it.

Examples:
    python update_review_flags.py --folder output/pages --pages 1,2,5-10
    python update_review_flags.py --folder output/pages --pages 140 --apply
    python update_review_flags.py --folder output/pages --pages 1-20 --status reviewed --apply

Page numbers refer to the dictionary's PRINTED page numbers, not original PDF
page numbers. This is determined from printed_page_number or the entries'
source_printed_page field where possible.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_pages(spec: str) -> set[int]:
    """Parse page specifications such as '1,3,5-8' into a set of integers."""
    pages: set[int] = set()
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            parts = item.split("-", maxsplit=1)
            if len(parts) != 2:
                raise ValueError(f"Invalid page range: {item!r}")
            start, end = int(parts[0]), int(parts[1])
            if start < 1 or end < start:
                raise ValueError(f"Invalid page range: {item!r}")
            pages.update(range(start, end + 1))
        else:
            page = int(item)
            if page < 1:
                raise ValueError(f"Page numbers must be positive: {item!r}")
            pages.add(page)
    if not pages:
        raise ValueError("No page numbers were supplied.")
    return pages


def get_printed_page(data: dict[str, Any], path: Path) -> int | None:
    """Find the printed page number from the document or its entries."""
    value = data.get("printed_page_number")
    if isinstance(value, int):
        return value

    entries = data.get("entries", [])
    if isinstance(entries, list):
        found = {
            entry.get("source_printed_page")
            for entry in entries
            if isinstance(entry, dict)
            and isinstance(entry.get("source_printed_page"), int)
        }
        if len(found) == 1:
            return found.pop()

    # Fallback for names such as page_140_validated.json or page_140.json.
    import re
    match = re.search(r"page[_-]?(\d+)", path.stem, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update human review flags in selected dictionary page JSON files."
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=Path("output/pages"),
        help="Folder containing page-level JSON files (default: output/pages).",
    )
    parser.add_argument(
        "--pages",
        required=True,
        help="Printed page numbers, e.g. 1,2,5-10,140.",
    )
    parser.add_argument(
        "--status",
        choices=("reviewed", "verified"),
        default="verified",
        help=(
            "'reviewed' sets review_required=false; "
            "'verified' sets review_required=false and human_verified=true "
            "(default: verified)."
        ),
    )
    parser.add_argument(
        "--pattern",
        default="*.json",
        help="File glob inside --folder (default: *.json).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write changes. Without this option, only preview changes.",
    )
    parser.add_argument(
        "--backup-folder",
        type=Path,
        default=None,
        help="Backup folder (default: <folder>/_review_flag_backups).",
    )
    args = parser.parse_args()

    try:
        target_pages = parse_pages(args.pages)
    except ValueError as exc:
        parser.error(str(exc))

    folder = args.folder
    if not folder.is_dir():
        print(f"ERROR: Folder does not exist: {folder}", file=sys.stderr)
        print("Pass the folder that contains your validated page JSON files with --folder.")
        return 2

    backup_folder = args.backup_folder or (folder / "_review_flag_backups")
    candidates = sorted(
        p for p in folder.glob(args.pattern)
        if p.is_file() and backup_folder not in p.parents
    )

    matched_pages: set[int] = set()
    files_changed = 0
    entries_changed = 0
    entries_already_set = 0
    errors = 0

    print("MODE:", "APPLY CHANGES" if args.apply else "DRY RUN (no files will be changed)")
    print("Folder:", folder.resolve())
    print("Target printed pages:", ", ".join(map(str, sorted(target_pages))))
    print("Status:", args.status)
    print()

    for path in candidates:
        try:
            original_text = path.read_text(encoding="utf-8-sig")
            data = json.loads(original_text)
            if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
                continue

            page_number = get_printed_page(data, path)
            if page_number not in target_pages:
                continue

            matched_pages.add(page_number)
            page_entry_changes = 0
            page_already_set = 0

            for entry in data["entries"]:
                if not isinstance(entry, dict):
                    continue

                desired = {"review_required": False}
                if args.status == "verified":
                    desired["human_verified"] = True

                if all(entry.get(key) == value for key, value in desired.items()):
                    page_already_set += 1
                    continue

                entry.update(desired)
                page_entry_changes += 1

            if page_entry_changes:
                files_changed += 1
                entries_changed += page_entry_changes
                print(
                    f"{path.name}: printed page {page_number} — "
                    f"{page_entry_changes} entr(y/ies) would be updated"
                )
                if args.apply:
                    backup_folder.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = backup_folder / f"{path.stem}.{timestamp}.bak.json"
                    # Avoid overwriting a backup if two files are processed within one second.
                    counter = 1
                    while backup_path.exists():
                        backup_path = backup_folder / (
                            f"{path.stem}.{timestamp}.{counter}.bak.json"
                        )
                        counter += 1
                    shutil.copy2(path, backup_path)
                    path.write_text(
                        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
            else:
                print(
                    f"{path.name}: printed page {page_number} — "
                    "all entries already have the requested flags"
                )

            entries_already_set += page_already_set

        except (OSError, json.JSONDecodeError) as exc:
            errors += 1
            print(f"ERROR reading {path.name}: {exc}", file=sys.stderr)

    missing_pages = sorted(target_pages - matched_pages)
    print("\nSummary")
    print("-------")
    print("Files with changes:", files_changed)
    print("Entries to update / updated:", entries_changed)
    print("Entries already set:", entries_already_set)
    if missing_pages:
        print("WARNING: No matching JSON file found for printed page(s):",
              ", ".join(map(str, missing_pages)))
        print("Check --folder, --pattern, and whether filenames/page metadata use printed page numbers.")
    if errors:
        print("Files with errors:", errors)
    if not args.apply:
        print("\nNothing was changed. Review the preview, then rerun with --apply.")
    else:
        print("\nChanges applied. Original files were backed up in:", backup_folder.resolve())

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
