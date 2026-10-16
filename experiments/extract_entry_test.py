
import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from nupe_to_eng_textprocessor.models import DictionaryEntry


# Load the API key from the project's .env file.
load_dotenv()

# Change this to the filename of your complete-entry crop.
IMAGE_PATH = Path("data/headword_crops/single_entry.png")

RAW_OUTPUT_PATH = Path("output/complete_entry_raw.json")
VALIDATED_OUTPUT_PATH = Path("output/complete_entry_validated.json")

MODEL = "gpt-6-astra"


PROMPT = """
Transcribe the complete dictionary entry visible in the image.

The dictionary has these columns:
1. Nupe: headword
2. PoS: part of speech
3. C: category code
4. English: English definition
5. Additional information: notes, examples, scientific names,
   alternative spellings, and cross-references.

Return exactly one JSON object with these fields:

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

Rules:
- Preserve the Nupe headword exactly, including every diacritic.
- Preserve the wording and punctuation of the English definition.
- Copy PoS and category codes exactly as printed.
- Use null when PoS or category code is absent or unreadable.
- Put alternative spellings in alternative_spellings only when
  the source explicitly identifies them as alternatives.
- Preserve notes, examples, scientific names, and cross-references
  in additional_information.
- If the entry contains multiple distinct senses, create a
  separate object for each sense.
- Do not invent missing information.
- If any text is unclear, mark it with [?] and flag the entry
  for review.
- source_excerpt should contain a transcription of the visible
  entry, not a description of the image.
- Return JSON only, without Markdown fences or explanations.

SECTION HEADINGS AND ENTRY BOUNDARIES:
- The dictionary may contain standalone numbers, letters,
  or symbols that mark the beginning of a new section.
- These markers are organizational headings, not dictionary
  entries. Do not extract them as headwords.
- Extract every genuine dictionary entry that appears below
  or around these markers.
- Do not merge separate entries merely because they have
  identical headwords.
- Preserve each entry's own part of speech, category code,
  definition, and additional information.
- Preserve cross-references exactly as printed.
"""


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing from .env.")

    if not IMAGE_PATH.is_file():
        raise FileNotFoundError(
            f"Image not found: {IMAGE_PATH.resolve()}"
        )

    suffix = IMAGE_PATH.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }

    if suffix not in mime_types:
        raise ValueError("Image must be PNG or JPEG.")

    image_bytes = IMAGE_PATH.read_bytes()
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    client = OpenAI()

    print(f"Extracting entry from {IMAGE_PATH.name}...", flush=True)

    response = client.responses.create(
        model=MODEL,
        instructions=(
            "You are transcribing a historical bilingual dictionary. "
            "Prioritize faithful transcription over interpretation. "
            "Preserve Unicode characters and do not guess unclear text."
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
        max_output_tokens=2500,
    )

    if response.status != "completed":
        raise RuntimeError(
            f"API response did not complete: {response.status}"
        )

    raw = response.output_text or ""

    if not raw.strip():
        raise RuntimeError("OpenAI returned an empty response.")

    # Preserve the original response for auditing.
    RAW_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUT_PATH.write_text(raw, encoding="utf-8")

    print(f"Raw response saved to: {RAW_OUTPUT_PATH}")

    if response.usage:
        print(f"Input tokens: {response.usage.input_tokens}")
        print(f"Output tokens: {response.usage.output_tokens}")

    # Parse JSON. Do not silently repair malformed output.
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Model did not return valid JSON. "
            f"Raw response saved to {RAW_OUTPUT_PATH}."
        ) from exc

    # Attach source metadata locally rather than asking the model
    # to guess page numbers or review status.
    data["source_pdf_page"] = 7
    data["source_printed_page"] = 3
    data["review_required"] = True
    data["human_verified"] = False

    # Validate the extracted entry against the existing schema.
    entry = DictionaryEntry.model_validate(data)

    # Save the validated structure.
    VALIDATED_OUTPUT_PATH.write_text(
        entry.model_dump_json(indent=2),
        encoding="utf-8",
    )

    print(f"Validated entry saved to: {VALIDATED_OUTPUT_PATH}")
    print("\n--- VALIDATED ENTRY ---")
    print(entry.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
