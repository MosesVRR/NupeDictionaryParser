
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = PROJECT_DIR / "output" / "validated"

OUTPUT_DIR = PROJECT_DIR / "output" / "reconciliation"
OUTPUT_FILE = OUTPUT_DIR / "boundary_review_pilot.json"

MODEL = "gpt-6-astra"  # Reuse the model from your existing scripts.
PILOT_BOUNDARIES = 10
MAX_OUTPUT_TOKENS = 1500

if INPUT_DIR is None:
    raise FileNotFoundError(
        "Could not find output/pages or output/validated."
    )

client = OpenAI()


# --------------------------------------------------
# Load page JSON files
# --------------------------------------------------

def load_pages():
    """Load canonical validated page files in filename order."""

    files = sorted(INPUT_DIR.glob("page_*_validated.json"))

    if not files:
        raise FileNotFoundError(
            f"No page_*_validated.json files found in {INPUT_DIR}"
        )

    pages = []

    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Skipping unreadable file {path.name}: {exc}")
            continue

        if not isinstance(data, dict) or not isinstance(
            data.get("entries"), list
        ):
            print(f"Skipping unexpected JSON structure: {path.name}")
            continue

        pages.append({
            "filename": path.name,
            "data": data,
        })

    if len(pages) < 2:
        raise ValueError("At least two valid page files are required.")

    return pages


def entry_summary(entry):
    """Keep boundary context concise to reduce token usage."""

    return {
        "headword": entry.get("headword"),
        "alternative_spellings": entry.get("alternative_spellings", []),
        "senses": entry.get("senses", []),
        "additional_information": entry.get("additional_information", []),
        "source_page": entry.get("source_page"),
        "source_excerpt": entry.get("source_excerpt"),
        "review_required": entry.get("review_required"),
    }


def page_summary(page, edge):
    """
    Include notes and entries nearest the requested boundary.
    For the previous page, inspect its ending.
    For the next page, inspect its beginning.
    """

    data = page["data"]
    entries = data.get("entries", [])

    if edge == "ending":
        selected = entries[-5:]
    elif edge == "beginning":
        selected = entries[:5]
    else:
        selected = entries

    return {
        "filename": page["filename"],
        "pdf_page_number": data.get("pdf_page_number"),
        "printed_page_number": data.get("printed_page_number"),
        "page_number": data.get("page_number"),
        "page_notes": data.get("page_notes", []),
        "boundary_entries": [
            entry_summary(entry) for entry in selected
        ],
    }


# --------------------------------------------------
# Ask the model to investigate one page boundary
# --------------------------------------------------

def review_boundary(previous_page, next_page):
    previous = page_summary(previous_page, "ending")
    following = page_summary(next_page, "beginning")

    prompt = f"""
You are assisting with quality control for a scanned Nupe-English
dictionary. The supplied JSON was previously extracted and validated,
but its transcription may contain errors.

Investigate the boundary between these two consecutive extracted pages.

PREVIOUS PAGE (ending):
{json.dumps(previous, ensure_ascii=False)}

NEXT PAGE (beginning):
{json.dumps(following, ensure_ascii=False)}

Your task:
1. Inspect page notes, additional information, source excerpts,
   review flags, and the entries near the boundary.
2. Determine whether there is evidence that an entry or definition
   continues across the page boundary.
3. Do not assume that similar headwords are the same entry.
4. Do not merge entries merely because a definition looks incomplete.
5. If the JSON does not provide enough evidence, request visual
   verification rather than guessing.
6. Propose a correction only when there is specific supporting evidence.
7. Do not rewrite the entire page or invent missing dictionary text.

Return ONLY a valid JSON object with these keys:
{{
  "boundary": "previous_filename -> next_filename",
  "finding": "continuation_likely | no_issue_found | uncertain",
  "confidence": "high | medium | low",
  "evidence": ["specific evidence from the supplied JSON"],
  "proposed_action": "A precise proposed action, or no change",
  "target_page": "filename or null",
  "target_headword": "headword or null",
  "target_field": "field name or null",
  "proposed_replacement": "exact replacement or null",
  "needs_visual_verification": true,
  "reason_visual_verification_needed": "reason or null"
}}

Important:
- This is a review proposal, not an instruction to edit files.
- Set needs_visual_verification to true whenever the original scan
  is needed to establish the correct reading or entry structure.
- If evidence is insufficient, set finding to "uncertain".
- Do not claim that you inspected the original scanned PDF.
"""

    response = client.responses.create(
        model=MODEL,
        input=prompt,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    usage = getattr(response, "usage", None)

    input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage else 0

    raw_text = response.output_text.strip()

    # Fail safely if the model returns malformed JSON.
    try:
        proposal = json.loads(raw_text)
    except json.JSONDecodeError:
        proposal = {
            "boundary": (
                f"{previous_page['filename']} -> "
                f"{next_page['filename']}"
            ),
            "finding": "uncertain",
            "confidence": "low",
            "evidence": [],
            "proposed_action": "Model response was not valid JSON.",
            "target_page": None,
            "target_headword": None,
            "target_field": None,
            "proposed_replacement": None,
            "needs_visual_verification": True,
            "reason_visual_verification_needed": (
                "The response needs manual inspection."
            ),
            "raw_response": raw_text,
        }

    # Conservative safety rule:
    # The model cannot waive image verification when it proposes
    # a continuation based on text recorded in page notes.
    if proposal.get("finding") == "continuation_likely":
        proposal["needs_visual_verification"] = True

        if not proposal.get("reason_visual_verification_needed"):
            proposal["reason_visual_verification_needed"] = (
                "All proposed page-boundary continuations require "
                "verification against the original scan before editing."
            )
    # Add usage metadata without changing source files.
    proposal["_usage"] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }

    return proposal


# --------------------------------------------------
# Run a small, read-only pilot
# --------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = load_pages()

    # Each request investigates the boundary between two
    # consecutive files. The pilot makes at most 10 requests.
    boundaries = list(zip(pages[:-1], pages[1:]))
    boundaries = boundaries[:PILOT_BOUNDARIES]

    report = {
        "input_directory": str(INPUT_DIR),
        "model": MODEL,
        "pilot_boundaries_requested": len(boundaries),
        "source_files_modified": False,
        "results": [],
        "usage_totals": {
            "input_tokens": 0,
            "output_tokens": 0,
        },
    }

    for index, (previous_page, next_page) in enumerate(
        boundaries, start=1
    ):
        print(
            f"[{index}/{len(boundaries)}] Reviewing "
            f"{previous_page['filename']} -> "
            f"{next_page['filename']}"
        )

        try:
            result = review_boundary(previous_page, next_page)
        except Exception as exc:
            result = {
                "boundary": (
                    f"{previous_page['filename']} -> "
                    f"{next_page['filename']}"
                ),
                "finding": "uncertain",
                "confidence": "low",
                "proposed_action": "Review request failed.",
                "error": str(exc),
            }

        usage = result.get("_usage", {})
        report["usage_totals"]["input_tokens"] += usage.get(
            "input_tokens", 0
        )
        report["usage_totals"]["output_tokens"] += usage.get(
            "output_tokens", 0
        )

        report["results"].append(result)

        print(f"  Finding: {result.get('finding', 'uncertain')}")
        print(f"  Confidence: {result.get('confidence', 'unknown')}")

    OUTPUT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nPilot complete.")
    print(f"Input folder: {INPUT_DIR}")
    print(f"Report saved to: {OUTPUT_FILE}")
    print(f"Input tokens: {report['usage_totals']['input_tokens']}")
    print(f"Output tokens: {report['usage_totals']['output_tokens']}")
    print("No validated JSON files were modified.")


if __name__ == "__main__":
    main()
