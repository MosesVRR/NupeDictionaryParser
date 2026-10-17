#!/usr/bin/env python3
"""Import output/master_dictionary.jsonl into a normalized SQLite database.

Reads the JSONL without modifying it. Refuses to overwrite an existing database
unless --replace is supplied. If replacing, preserves the prior DB as a backup.
"""
from __future__ import annotations
import argparse, json, os, sqlite3, sys, tempfile
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE entries (
 entry_id INTEGER PRIMARY KEY,
 record_id TEXT NOT NULL UNIQUE,
 headword TEXT NOT NULL,
 source_printed_page INTEGER,
 source_pdf_page INTEGER,
 source_file TEXT,
 source_excerpt TEXT,
 review_required INTEGER NOT NULL CHECK(review_required IN (0,1)),
 human_verified INTEGER NOT NULL CHECK(human_verified IN (0,1)),
 entry_json TEXT NOT NULL
);
CREATE INDEX idx_entries_headword ON entries(headword COLLATE NOCASE);
CREATE INDEX idx_entries_page ON entries(source_printed_page);
CREATE INDEX idx_entries_review ON entries(review_required);
CREATE INDEX idx_entries_verified ON entries(human_verified);
CREATE TABLE senses (
 sense_id INTEGER PRIMARY KEY,
 entry_id INTEGER NOT NULL REFERENCES entries(entry_id) ON DELETE CASCADE,
 sense_order INTEGER NOT NULL,
 part_of_speech TEXT,
 definition_en TEXT NOT NULL,
 category_code TEXT,
 UNIQUE(entry_id, sense_order)
);
CREATE INDEX idx_senses_pos ON senses(part_of_speech);
CREATE INDEX idx_senses_definition ON senses(definition_en);
CREATE INDEX idx_senses_category ON senses(category_code);
CREATE TABLE alternative_spellings (
 spelling_id INTEGER PRIMARY KEY,
 entry_id INTEGER NOT NULL REFERENCES entries(entry_id) ON DELETE CASCADE,
 spelling_order INTEGER NOT NULL,
 spelling TEXT NOT NULL,
 UNIQUE(entry_id, spelling_order)
);
CREATE INDEX idx_alt_spelling ON alternative_spellings(spelling COLLATE NOCASE);
CREATE TABLE additional_information (
 information_id INTEGER PRIMARY KEY,
 entry_id INTEGER NOT NULL REFERENCES entries(entry_id) ON DELETE CASCADE,
 information_order INTEGER NOT NULL,
 information TEXT NOT NULL,
 UNIQUE(entry_id, information_order)
);
"""

def as_bool(value: Any, default: bool) -> bool:
    if value is None: return default
    if isinstance(value, bool): return value
    if value in (0, 1): return bool(value)
    raise ValueError(f"Expected boolean/0/1, got {value!r}")

def optional_int(value: Any, field: str):
    if value is None: return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer or null, got {value!r}")
    return value

def import_dataset(input_path: Path, db_path: Path, replace_existing: bool,
                   reject_placeholders: bool) -> dict[str, Any]:
    if not input_path.is_file():
        raise FileNotFoundError(f"Master JSONL not found: {input_path.resolve()}")
    if db_path.exists() and not replace_existing:
        raise FileExistsError(
            f"Database already exists: {db_path.resolve()}\n"
            "Choose another --database path or pass --replace to rebuild it."
        )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{db_path.stem}_",
        suffix=".tmp.sqlite3", dir=str(db_path.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    counts = Counter()
    problems = []
    seen_ids = set()
    placeholder_records = 0
    try:
        conn = sqlite3.connect(temp_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(SCHEMA)
            conn.execute("BEGIN")
            with input_path.open("r", encoding="utf-8-sig") as source:
                for line_no, line in enumerate(source, start=1):
                    if not line.strip():
                        problems.append({"line": line_no, "issue": "blank line skipped"})
                        counts["blank_lines"] += 1
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
                    if not isinstance(record, dict):
                        raise ValueError(f"Line {line_no}: record must be a JSON object")
                    record_id, headword, senses = (
                        record.get("record_id"), record.get("headword"), record.get("senses"))
                    if not isinstance(record_id, str) or not record_id.strip():
                        raise ValueError(f"Line {line_no}: missing/empty record_id")
                    if record_id in seen_ids:
                        raise ValueError(f"Line {line_no}: duplicate record_id {record_id!r}")
                    seen_ids.add(record_id)
                    if not isinstance(headword, str) or not headword.strip():
                        raise ValueError(f"Line {line_no}: missing/empty headword")
                    if not isinstance(senses, list):
                        raise ValueError(f"Line {line_no}: senses must be a list")
                    if "[?]" in json.dumps(record, ensure_ascii=False):
                        placeholder_records += 1
                        if reject_placeholders:
                            raise ValueError(f"Line {line_no}: literal '[?]' placeholder found")
                    printed = optional_int(record.get("source_printed_page"), "source_printed_page")
                    pdf_page = optional_int(record.get("source_pdf_page"), "source_pdf_page")
                    review = as_bool(record.get("review_required"), True)
                    verified = as_bool(record.get("human_verified"), False)
                    cur = conn.execute("""INSERT INTO entries
                      (record_id,headword,source_printed_page,source_pdf_page,source_file,
                       source_excerpt,review_required,human_verified,entry_json)
                      VALUES (?,?,?,?,?,?,?,?,?)""",
                      (record_id, headword, printed, pdf_page, record.get("source_file"),
                       record.get("source_excerpt"), int(review), int(verified),
                       json.dumps(record, ensure_ascii=False, separators=(",", ":"))))
                    entry_id = cur.lastrowid
                    counts["entries"] += 1
                    for sense_i, sense in enumerate(senses, start=1):
                        if not isinstance(sense, dict):
                            raise ValueError(f"Line {line_no}, sense {sense_i}: must be an object")
                        definition = sense.get("definition_en")
                        if not isinstance(definition, str):
                            raise ValueError(f"Line {line_no}, sense {sense_i}: definition_en must be a string")
                        conn.execute("""INSERT INTO senses
                          (entry_id,sense_order,part_of_speech,definition_en,category_code)
                          VALUES (?,?,?,?,?)""",
                          (entry_id, sense_i, sense.get("part_of_speech"), definition,
                           sense.get("category_code")))
                        counts["senses"] += 1
                    spellings = record.get("alternative_spellings", [])
                    if spellings is None: spellings = []
                    if not isinstance(spellings, list):
                        raise ValueError(f"Line {line_no}: alternative_spellings must be a list")
                    for i, spelling in enumerate(spellings, start=1):
                        if not isinstance(spelling, str):
                            raise ValueError(f"Line {line_no}: spelling must be a string")
                        conn.execute("INSERT INTO alternative_spellings(entry_id,spelling_order,spelling) VALUES (?,?,?)",
                                     (entry_id, i, spelling))
                        counts["alternative_spellings"] += 1
                    infos = record.get("additional_information", [])
                    if infos is None: infos = []
                    if not isinstance(infos, list):
                        raise ValueError(f"Line {line_no}: additional_information must be a list")
                    for i, info in enumerate(infos, start=1):
                        if not isinstance(info, str):
                            raise ValueError(f"Line {line_no}: additional-information item must be a string")
                        conn.execute("INSERT INTO additional_information(entry_id,information_order,information) VALUES (?,?,?)",
                                     (entry_id, i, info))
                        counts["additional_information"] += 1
            conn.commit()
            if conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] != counts["entries"]:
                raise RuntimeError("Entry row count check failed")
            if conn.execute("SELECT COUNT(*) FROM senses").fetchone()[0] != counts["senses"]:
                raise RuntimeError("Sense row count check failed")
            fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_errors: raise RuntimeError(f"Foreign key check failed: {fk_errors[:10]}")
            conn.execute("PRAGMA optimize")
        finally:
            conn.close()
        if db_path.exists() and replace_existing:
            backup = db_path.with_suffix(db_path.suffix + ".bak")
            i = 2
            while backup.exists():
                backup = db_path.with_suffix(db_path.suffix + f".bak{i}")
                i += 1
            db_path.replace(backup)
            print("Previous database backed up to:", backup.resolve())
        temp_path.replace(db_path)
    except Exception:
        if temp_path.exists(): temp_path.unlink()
        raise
    return {"input_file": str(input_path.resolve()), "database_file": str(db_path.resolve()),
            "counts": dict(counts), "placeholder_records": placeholder_records,
            "warnings": problems, "foreign_key_check": "passed"}

def main() -> int:
    parser = argparse.ArgumentParser(description="Import Nupe dictionary JSONL into SQLite.")
    parser.add_argument("--input", type=Path, default=Path("output/master_dictionary.jsonl"))
    parser.add_argument("--database", type=Path, default=Path("output/nupe_dictionary.sqlite3"))
    parser.add_argument("--report", type=Path, default=Path("output/sqlite_import_report.json"))
    parser.add_argument("--replace", action="store_true",
                        help="Replace existing database; old DB is backed up first.")
    parser.add_argument("--reject-placeholders", action="store_true",
                        help="Stop if a literal '[?]' remains in any record.")
    args = parser.parse_args()
    try:
        report = import_dataset(args.input, args.database, args.replace, args.reject_placeholders)
    except Exception as exc:
        print(f"IMPORT FAILED: {exc}", file=sys.stderr)
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    c = report["counts"]
    print("\nSQLITE IMPORT COMPLETE\n======================")
    print("Entries imported:", c.get("entries", 0))
    print("Senses imported:", c.get("senses", 0))
    print("Alternative spellings imported:", c.get("alternative_spellings", 0))
    print("Additional-information items imported:", c.get("additional_information", 0))
    print("Records containing literal '[?]':", report["placeholder_records"])
    print("Foreign-key integrity:", report["foreign_key_check"])
    print("Database:", report["database_file"])
    print("Import report:", args.report.resolve())
    if report["placeholder_records"]:
        print("NOTE: placeholder records remain; review them if unexpected.")
    if report["warnings"]:
        print("Blank lines or warnings recorded:", len(report["warnings"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
