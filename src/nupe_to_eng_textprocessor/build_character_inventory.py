#!/usr/bin/env python3
"""Build character and combining-sequence inventories from Nupe master JSONL.

Run from the repository root:
  python src/nupe_to_eng_textprocessor/build_character_inventory.py

Reads output/master_dictionary.jsonl and does not modify the source.
Writes:
  output/character_inventory.json
  output/character_inventory.csv
  output/character_sequences.json
  output/character_sequences.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


DIACRITIC_NAME_TERMS = (
    "WITH ACUTE", "WITH GRAVE", "WITH CIRCUMFLEX", "WITH CARON",
    "WITH TILDE", "WITH MACRON", "WITH DOT", "WITH DIAERESIS",
    "WITH BREVE", "WITH RING", "WITH HOOK", "WITH HORN",
    "WITH OGONEK", "WITH CEDILLA", "WITH STROKE",
)


def classify_character(char: str) -> str:
    category = unicodedata.category(char)
    if category.startswith("L"):
        name = unicodedata.name(char, "")
        if any(term in name for term in DIACRITIC_NAME_TERMS):
            return "letter_with_diacritic_or_modifier"
        return "letter"
    if category.startswith("M"):
        return "combining_mark"
    if category.startswith("N"):
        return "digit_or_number"
    if category.startswith("P"):
        return "punctuation"
    if category.startswith("Z") or char.isspace():
        return "whitespace"
    if category.startswith("S"):
        return "symbol"
    if category.startswith("C"):
        return "control_or_format"
    return "other"


def display_character(char: str) -> str:
    if char == " ":
        return "<SPACE>"
    if char == "\t":
        return "<TAB>"
    if char == "\n":
        return "<NEWLINE>"
    if char == "\r":
        return "<CARRIAGE RETURN>"
    if unicodedata.category(char).startswith("C"):
        return f"<{unicodedata.name(char, 'UNNAMED CONTROL')}>"
    return char


def code_points(text: str) -> list[str]:
    return [f"U+{ord(char):04X}" for char in text]


def grapheme_like_clusters(text: str) -> list[str]:
    """Group each Unicode combining mark with the preceding code point.

    This is a practical inventory method for orthographic sequences, not a full
    implementation of Unicode grapheme-cluster segmentation.
    """
    clusters: list[str] = []
    for char in text:
        if unicodedata.category(char).startswith("M") and clusters:
            clusters[-1] += char
        else:
            clusters.append(char)
    return clusters


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory Unicode characters and combining sequences in headwords."
    )
    parser.add_argument("--input", default="output/master_dictionary.jsonl")
    parser.add_argument("--json-output", default="output/character_inventory.json")
    parser.add_argument("--csv-output", default="output/character_inventory.csv")
    parser.add_argument("--sequences-json-output", default="output/character_sequences.json")
    parser.add_argument("--sequences-csv-output", default="output/character_sequences.csv")
    args = parser.parse_args()

    input_path = Path(args.input)
    json_path = Path(args.json_output)
    csv_path = Path(args.csv_output)
    sequences_json_path = Path(args.sequences_json_output)
    sequences_csv_path = Path(args.sequences_csv_output)

    if not input_path.is_file():
        parser.error(f"Input file not found: {input_path}")

    char_occurrences: Counter[str] = Counter()
    char_headword_counts: Counter[str] = Counter()
    char_examples: dict[str, str] = {}

    seq_occurrences: Counter[str] = Counter()
    seq_headword_counts: Counter[str] = Counter()
    seq_examples: dict[str, str] = {}

    entry_count = 0
    missing_headword_count = 0
    malformed_lines: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                malformed_lines.append({"line": line_number, "error": str(exc)})
                continue
            if not isinstance(entry, dict):
                malformed_lines.append({
                    "line": line_number,
                    "error": "JSONL record is not an object",
                })
                continue

            headword = entry.get("headword")
            if not isinstance(headword, str) or not headword:
                missing_headword_count += 1
                continue

            entry_count += 1
            # Exact code-point counts; source headwords are never normalized.
            char_occurrences.update(headword)
            char_headword_counts.update(set(headword))
            for char in set(headword):
                char_examples.setdefault(char, headword)

            clusters = grapheme_like_clusters(headword)
            seq_occurrences.update(clusters)
            seq_headword_counts.update(set(clusters))
            for sequence in set(clusters):
                seq_examples.setdefault(sequence, headword)

    character_rows = []
    classification_counts: Counter[str] = Counter()
    for char in sorted(char_occurrences, key=lambda c: (unicodedata.name(c, "UNNAMED"), ord(c))):
        classification = classify_character(char)
        classification_counts[classification] += 1
        character_rows.append({
            "character": char,
            "display": display_character(char),
            "code_point": f"U+{ord(char):04X}",
            "decimal_code_point": ord(char),
            "unicode_name": unicodedata.name(char, "UNNAMED"),
            "unicode_category": unicodedata.category(char),
            "classification": classification,
            "occurrences": char_occurrences[char],
            "headwords_containing_character": char_headword_counts[char],
            "example_headword": char_examples.get(char, ""),
        })

    sequence_rows = []
    for sequence in sorted(
        seq_occurrences,
        key=lambda s: (tuple(ord(c) for c in s), len(s)),
    ):
        marks = [
            {
                "character": char,
                "code_point": f"U+{ord(char):04X}",
                "unicode_name": unicodedata.name(char, "UNNAMED"),
            }
            for char in sequence
        ]
        has_combining_mark = any(
            unicodedata.category(char).startswith("M") for char in sequence
        )
        sequence_rows.append({
            "sequence": sequence,
            "display": "".join(display_character(c) for c in sequence),
            "code_points": code_points(sequence),
            "unicode_names": [unicodedata.name(c, "UNNAMED") for c in sequence],
            "contains_combining_mark": has_combining_mark,
            "is_multi_code_point_sequence": len(sequence) > 1,
            "occurrences": seq_occurrences[sequence],
            "headwords_containing_sequence": seq_headword_counts[sequence],
            "example_headword": seq_examples.get(sequence, ""),
        })

    summary = {
        "source_file": str(input_path),
        "source_is_modified": False,
        "valid_entries_with_headwords": entry_count,
        "records_missing_headword": missing_headword_count,
        "malformed_or_non_object_records": len(malformed_lines),
    }

    char_result = {
        **summary,
        "counting_note": (
            "Exact Unicode code points counted as stored; no Unicode normalization "
            "is applied. This file lists individual code points."
        ),
        "summary": {
            **summary,
            "unique_code_points": len(character_rows),
            "classification_counts": dict(sorted(classification_counts.items())),
        },
        "characters": character_rows,
        "malformed_lines": malformed_lines,
    }
    sequence_result = {
        **summary,
        "counting_note": (
            "A sequence is a code point followed by any immediately following "
            "Unicode combining marks. This is intended to expose written forms "
            "such as a precomposed vowel plus an additional combining diacritic. "
            "It is not a complete Unicode grapheme-segmentation algorithm. "
            "Source text is not normalized or modified."
        ),
        "summary": {
            **summary,
            "unique_sequences": len(sequence_rows),
            "sequences_with_combining_marks": sum(
                row["contains_combining_mark"] for row in sequence_rows
            ),
            "multi_code_point_sequences": sum(
                row["is_multi_code_point_sequence"] for row in sequence_rows
            ),
        },
        "sequences": sequence_rows,
        "malformed_lines": malformed_lines,
    }

    for path in (json_path, csv_path, sequences_json_path, sequences_csv_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    with json_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(char_result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with sequences_json_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(sequence_result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    char_fields = [
        "character", "display", "code_point", "decimal_code_point",
        "unicode_name", "unicode_category", "classification", "occurrences",
        "headwords_containing_character", "example_headword",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=char_fields)
        writer.writeheader()
        writer.writerows(character_rows)

    seq_fields = [
        "sequence", "display", "code_points", "unicode_names",
        "contains_combining_mark", "is_multi_code_point_sequence",
        "occurrences", "headwords_containing_sequence", "example_headword",
    ]
    with sequences_csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=seq_fields)
        writer.writeheader()
        for row in sequence_rows:
            flattened = dict(row)
            flattened["code_points"] = " + ".join(row["code_points"])
            flattened["unicode_names"] = " + ".join(row["unicode_names"])
            writer.writerow({field: flattened[field] for field in seq_fields})

    print(f"Input: {input_path}")
    print(f"Valid entries with headwords: {entry_count:,}")
    print(f"Records missing headword: {missing_headword_count:,}")
    print(f"Malformed/non-object records: {len(malformed_lines):,}")
    print(f"Unique Unicode code points: {len(character_rows):,}")
    print(f"Unique character sequences: {len(sequence_rows):,}")
    print(f"Sequences with combining marks: {sequence_result['summary']['sequences_with_combining_marks']:,}")
    print(f"JSON character report: {json_path}")
    print(f"CSV character report:  {csv_path}")
    print(f"JSON sequence report:  {sequences_json_path}")
    print(f"CSV sequence report:   {sequences_csv_path}")
    print("\nMulti-code-point sequences containing combining marks:")
    for row in sequence_rows:
        if row["contains_combining_mark"] and row["is_multi_code_point_sequence"]:
            print(
                f"{row['display']:<12} {' + '.join(row['code_points']):<24} "
                f"occurrences={row['occurrences']:<7,} "
                f"headwords={row['headwords_containing_sequence']:,} "
                f"example={row['example_headword']}"
            )

    if malformed_lines or missing_headword_count:
        print("\nReview the JSON reports for records excluded from the inventory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
