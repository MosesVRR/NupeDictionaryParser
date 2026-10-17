import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from nupe_to_eng_textprocessor.models import DictionaryEntry, DictionaryPage


load_dotenv()

IMAGE_PATH = Path("output/pages/page_140_450dpi.png")
RAW_OUTPUT_PATH = Path("output/page_140_raw.json")
VALIDATED_OUTPUT_PATH = Path("output/page_140_validated.json")

# Reduced PDF page 140 corresponds to original PDF page 144.
PDF_PAGE_NUMBER = 144
PRINTED_PAGE_NUMBER = 140

MODEL = "gpt-6-astra"
MAX_OUTPUT_TOKENS = 6000

PROMPT = """
Extract EVERY dictionary entry visible in the ENTIRE image, from the first
entry at the top to the final entry at the bottom.

The dictionary columns are:
1. Nupe: headword
2. PoS: part of speech
3. C: category code
4. English: English definition
5. Additional information: notes, examples, scientific names,
   alternative spellings, and cross-references.

Return a JSON object with this structure:
{
  "entries": [
    {
      "headword": "string",
      "alternative_spellings": [],
      "senses": [
        {
          "part_of_speech": null,
          "definition_en": "string",
          "category_code": null
        }
      ],
      "additional_information": [],
      "source_excerpt": "string"
    }
  ],
  "page_notes": []
}

IMPORTANT COMPLETENESS RULES:
- Do not stop after extracting the first entry or a small subset.
- Process the entire page, including the middle and bottom.
- Return every genuine entry in page order.
- Do not summarize, sample, or omit entries.
- This page contains many entries. Continue until all visible entries
  have been processed.
- Do not treat the page heading or printed page number as an entry.

TRANSCRIPTION RULES:
- Preserve all Nupe characters and diacritics exactly.
- Preserve the wording and punctuation of definitions.
- Copy PoS labels and category codes exactly as printed.
- Use null for a PoS or category code only when absent or unreadable.
- Preserve alternative spellings and cross-references.
- Do not merge distinct entries merely because their headwords
  are identical. Each distinct printed entry must remain separate.
- Represent distinct senses separately only when the printed layout
  supports that interpretation.
- Do not invent text that is not visible.
- Mark uncertain characters with [?] and note the uncertainty.
- Keep additional information separate from the English definition
  when the layout makes that distinction clear.

SECTION MARKERS:
- Standalone numbers, letters, or symbols used to indicate sections
  are not headwords. Do not extract them as dictionary entries.
- Continue extracting genuine entries around section markers.
- Put relevant section information in page_notes if useful.

SOURCE EXCERPTS:
- Preserve the visible text belonging to each entry.
- Do not invent missing text or page information.

PAGE BOUNDARIES:
- If text appears to continue an entry from an adjacent page, record
  that observation in page_notes.
- Do not invent missing text or silently merge across pages.

Return JSON only. Do not use Markdown fences or explanations.
"""


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing from .env.")

    if not IMAGE_PATH.is_file():
        raise FileNotFoundError(f"Image not found: {IMAGE_PATH.resolve()}")

    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    suffix = IMAGE_PATH.suffix.lower()
    if suffix not in mime_types:
        raise ValueError("Image must be PNG or JPEG.")

    encoded_image = base64.b64encode(IMAGE_PATH.read_bytes()).decode("utf-8")
    client = OpenAI()

    print(f"Extracting entries from {IMAGE_PATH.name}...", flush=True)

    response = client.responses.create(
        model=MODEL,
        instructions=(
            "You are transcribing a historical bilingual dictionary. "
            "Prioritize faithful transcription over guessing. Preserve Unicode "
            "characters, entry boundaries, and the distinction between section "
            "markers and headwords. Extract the entire page, not just its first "
            "few entries. Return only valid JSON matching the requested shape."
        ),
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": PROMPT},
                    {
                        "type": "input_image",
                        "image_url": (
                            f"data:{mime_types[suffix]};base64,{encoded_image}"
                        ),
                        "detail": "original",
                    },
                ],
            }
        ],
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    # Diagnostics help distinguish incomplete output from malformed JSON.
    print(f"Response status: {response.status}")
    print(f"Response ID: {response.id}")
    print(f"Incomplete details: {response.incomplete_details}")

    if response.error:
        print(f"API error: {response.error}")

    if response.usage:
        print(f"Input tokens: {response.usage.input_tokens}")
        print(f"Output tokens: {response.usage.output_tokens}")
        print("Output token details:", response.usage.output_tokens_details)

    raw = response.output_text or ""

    # Preserve raw output before checking status or parsing.
    RAW_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUT_PATH.write_text(raw, encoding="utf-8")
    print(f"Raw response saved to: {RAW_OUTPUT_PATH}")

    if response.status != "completed":
        raise RuntimeError(
            f"Response did not complete: {response.status}. "
            f"Inspect {RAW_OUTPUT_PATH} and the diagnostic output above."
        )

    if not raw.strip():
        raise RuntimeError(
            f"OpenAI returned an empty response. Inspect {RAW_OUTPUT_PATH}."
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON at line {exc.lineno}, column {exc.colno}. "
            f"Raw response saved to {RAW_OUTPUT_PATH}."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object at the top level.")
    if not isinstance(data.get("entries"), list):
        raise ValueError("The response must contain an entries list.")
    if not isinstance(data.get("page_notes", []), list):
        raise ValueError("page_notes must be a list.")

    # This page is visibly dense. Reject a suspiciously short extraction.
    # This threshold is specific to printed page 140, not a general rule.
    if PRINTED_PAGE_NUMBER == 140 and len(data["entries"]) < 10:
        raise RuntimeError(
            f"Suspiciously few entries extracted from printed page 140: "
            f"{len(data['entries'])}. No validated output was written. "
            "Inspect the raw response and try a different extraction strategy."
        )

    entries = []
    for item in data["entries"]:
        if not isinstance(item, dict):
            raise ValueError("Each item in entries must be a JSON object.")

        item = dict(item)
        item["source_pdf_page"] = PDF_PAGE_NUMBER
        item["source_printed_page"] = PRINTED_PAGE_NUMBER
        item["review_required"] = True
        item["human_verified"] = False
        entries.append(DictionaryEntry.model_validate(item))

    page = DictionaryPage(
        pdf_page_number=PDF_PAGE_NUMBER,
        printed_page_number=PRINTED_PAGE_NUMBER,
        entries=entries,
        page_notes=data.get("page_notes", []),
    )

    VALIDATED_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATED_OUTPUT_PATH.write_text(
        page.model_dump_json(indent=2),
        encoding="utf-8",
    )

    print(f"Validated JSON saved to: {VALIDATED_OUTPUT_PATH}")
    print(f"Entries extracted: {len(page.entries)}")

    print("\n--- EXTRACTED HEADWORDS ---")
    for index, entry in enumerate(page.entries, start=1):
        print(f"{index}. {entry.headword}")

    print("\nValidation successful.")
    print(
        "Note: schema validation and entry count do not prove transcription "
        "accuracy; compare the output with the page image."
    )


if __name__ == "__main__":
    main()
