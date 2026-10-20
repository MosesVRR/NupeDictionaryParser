#!/usr/bin/env python3
"""Generate app-ready Nupe character configuration from observed headwords.

Run from repository root:
  python src/nupe_to_eng_textprocessor/build_app_character_config.py

Reads output/master_dictionary.jsonl and writes output/app_character_config.json.
Only includes forms observed in headwords. It does not normalize or edit source data.
"""

from __future__ import annotations

import argparse
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


def clusters(text: str) -> list[str]:
    """Group each Unicode combining mark with the immediately preceding code point."""
    result: list[str] = []
    for char in text:
        if unicodedata.category(char).startswith("M") and result:
            result[-1] += char
        else:
            result.append(char)
    return result


def is_letter_cluster(cluster: str) -> bool:
    """True when a cluster starts with a Unicode letter."""
    return bool(cluster) and unicodedata.category(cluster[0]).startswith("L")


def code_points(text: str) -> list[str]:
    return [f"U+{ord(char):04X}" for char in text]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create an app character config from observed dictionary headwords."
    )
    parser.add_argument("--input", default="output/master_dictionary.jsonl")
    parser.add_argument("--output", default="output/app_character_config.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.is_file():
        parser.error(f"Input file not found: {input_path}")

    form_occurrences: Counter[str] = Counter()
    form_headwords: Counter[str] = Counter()
    form_examples: dict[str, str] = {}
    initial_occurrences: Counter[str] = Counter()
    initial_headwords: Counter[str] = Counter()
    initial_examples: dict[str, str] = {}
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
            observed_clusters = clusters(headword)
            letters_in_headword = [cluster for cluster in observed_clusters if is_letter_cluster(cluster)]

            # Keyboard forms: every distinct observed letter cluster, with frequency
            # and an example headword. Punctuation and whitespace are excluded.
            form_occurrences.update(letters_in_headword)
            form_headwords.update(set(letters_in_headword))
            for form in set(letters_in_headword):
                form_examples.setdefault(form, headword)

            # Browse index: only the first cluster, and only if it starts with a letter.
            if observed_clusters and is_letter_cluster(observed_clusters[0]):
                initial = observed_clusters[0]
                initial_occurrences[initial] += 1
                initial_headwords[initial] += 1
                initial_examples.setdefault(initial, headword)

    forms = []
    for form in sorted(form_occurrences, key=lambda value: (value.casefold(), value)):
        ascii_lowercase = len(form) == 1 and "a" <= form <= "z"
        forms.append({
            "text": form,
            "code_points": code_points(form),
            "unicode_names": [unicodedata.name(char, "UNNAMED") for char in form],
            "kind": "basic_letter" if ascii_lowercase else "special_or_modified_letter",
            "occurrences": form_occurrences[form],
            "headwords_containing_form": form_headwords[form],
            "example_headword": form_examples.get(form, ""),
        })

    alphabet_index = []
    for initial in sorted(initial_occurrences, key=lambda value: (value.casefold(), value)):
        alphabet_index.append({
            "text": initial,
            "code_points": code_points(initial),
            "unicode_names": [unicodedata.name(char, "UNNAMED") for char in initial],
            "headwords_starting_with_form": initial_headwords[initial],
            "example_headword": initial_examples.get(initial, ""),
        })

    config = {
        "schema_version": 1,
        "source_file": str(input_path),
        "generated_from_observed_data_only": True,
        "normalization_applied": False,
        "notes": [
            "Forms are observed Unicode letter clusters from headwords in the source file.",
            "Combining marks are grouped with the preceding code point; no Unicode normalization is applied.",
            "The list is descriptive, not a declaration that every observed form is linguistically valid.",
            "Punctuation and whitespace are excluded from keyboard forms.",
            "Alphabet index contains observed first letter clusters only; it does not define linguistic sort order.",
        ],
        "summary": {
            "valid_entries_with_headwords": entry_count,
            "records_missing_headword": missing_headword_count,
            "malformed_or_non_object_records": len(malformed_lines),
            "unique_keyboard_forms": len(forms),
            "unique_observed_initial_forms": len(alphabet_index),
        },
        "keyboard_forms": forms,
        "alphabet_index": alphabet_index,
        "malformed_lines": malformed_lines,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Input: {input_path}")
    print(f"Valid entries with headwords: {entry_count:,}")
    print(f"Unique keyboard forms observed: {len(forms):,}")
    print(f"Unique initial forms observed: {len(alphabet_index):,}")
    print(f"Malformed/non-object records: {len(malformed_lines):,}")
    print(f"Output: {output_path}")
    print("\nObserved keyboard forms:")
    for form in forms:
        print(
            f"{form['text']:<8} "
            f"{' + '.join(form['code_points']):<25} "
            f"{form['kind']:<30} "
            f"occurrences={form['occurrences']:,}"
        )
    if malformed_lines or missing_headword_count:
        print("\nReview malformed_lines and missing headwords in the output JSON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
