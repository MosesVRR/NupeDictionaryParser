
import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from nupe_to_eng_textprocessor.models import DictionaryEntry, DictionaryPage


load_dotenv()

# Input image: full-page crop containing headings and entries.
IMAGE_PATH = Path("output/pages/dictionary_page_1_450dpi.png")

# Output files.
RAW_OUTPUT_PATH = Path("output/full_page_1_raw.json")
VALIDATED_OUTPUT_PATH = Path("output/full_page_1_validated.json")

# Update these to match the source image.
PDF_PAGE_NUMBER = 206
PRINTED_PAGE_NUMBER = 202

MODEL = "gpt-6-astra"


PROMPT = """
Extract every dictionary entry visible in this image.

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

TRANSCRIPTION RULES:
- Transcribe every genuine dictionary entry, in page order.
- Preserve all Nupe characters and diacritics exactly.
- Preserve the wording and punctuation of definitions.
- Copy PoS labels and category codes exactly as printed.
- Use null for a PoS or category code only when it is absent
  or unreadable.
- Preserve alternative spellings and cross-references.
- Do not merge distinct entries merely because their headwords
  are identical. Each distinct printed entry must remain separate.
- If one headword has multiple distinct senses, represent them
  as separate sense objects within that entry only when the
  printed layout supports that interpretation.
- Do not invent text that is not visible.
- Mark uncertain characters with [?] and note the uncertainty.
- Keep additional information separate from the English definition
  when the layout makes that distinction clear.

SECTION MARKERS:
- Standalone numbers, letters, or symbols used to indicate
  dictionary sections are not headwords.
- Do not extract these section markers as dictionary entries.
- Continue extracting genuine entries that appear below or beside
  a section marker.
- Put relevant section information in page_notes if useful.

SOURCE EXCERPTS:
- Preserve the visible text belonging to each entry.
- Do not invent missing text or page information.

Return JSON only. Do not use Markdown code fences or explanations.
"""


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing from .env.")

    if not IMAGE_PATH.is_file():
        raise FileNotFoundError(
            f"Image not found: {IMAGE_PATH.resolve()}"
        )

    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }

    suffix = IMAGE_PATH.suffix.lower()

    if suffix not in mime_types:
        raise ValueError("Image must be PNG or JPEG.")

    image_bytes = IMAGE_PATH.read_bytes()
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    client = OpenAI()

    print(f"Extracting entries from {IMAGE_PATH.name}...", flush=True)

    response = client.responses.create(
        model=MODEL,
        instructions=(
            "You are transcribing a historical bilingual dictionary. "
            "Prioritize faithful transcription over guessing. "
            "Preserve Unicode characters, entry boundaries, and "
            "the distinction between section markers and headwords."
        ),
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": PROMPT,
                    },
                    {
                        "type": "input_image",
                        "image_url": (
                            f"data:{mime_types[suffix]};"
                            f"base64,{encoded_image}"
                        ),
                        "detail": "original",
                    },
                ],
            }
        ],
        max_output_tokens=6000,
    )

    if response.status != "completed":
        raise RuntimeError(
            f"Response did not complete: {response.status}"
        )

    raw = response.output_text or ""

    if not raw.strip():
        raise RuntimeError("OpenAI returned an empty response.")

    # Save the exact model response before parsing.
    RAW_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUT_PATH.write_text(raw, encoding="utf-8")

    print(f"Raw response saved to: {RAW_OUTPUT_PATH}")

    if response.usage:
        print(f"Input tokens: {response.usage.input_tokens}")
        print(f"Output tokens: {response.usage.output_tokens}")

    # Parse JSON without silently repairing malformed output.
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON. Raw response saved to {RAW_OUTPUT_PATH}."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object at the top level.")

    if not isinstance(data.get("entries"), list):
        raise ValueError("The response must contain an entries list.")

    if not isinstance(data.get("page_notes", []), list):
        raise ValueError("page_notes must be a list.")

    # Attach source metadata locally.
    for item in data["entries"]:
        item["source_pdf_page"] = PDF_PAGE_NUMBER
        item["source_printed_page"] = PRINTED_PAGE_NUMBER
        item["review_required"] = True
        item["human_verified"] = False

    # Validate every entry using the existing Pydantic schema.
    entries = [
        DictionaryEntry.model_validate(item)
        for item in data["entries"]
    ]

    page = DictionaryPage(
        pdf_page_number=PDF_PAGE_NUMBER,
        printed_page_number=PRINTED_PAGE_NUMBER,
        entries=entries,
        page_notes=data.get("page_notes", []),
    )

    # Save validated JSON.
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
    print("\n--- VALIDATED JSON ---")
    print(page.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
