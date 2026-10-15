
import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from nupe_to_eng_textprocessor.models import DictionaryPage


# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()

image_path = Path("output/dictionary_page_1.png")
json_path = Path("output/dictionary_page_1.json")
raw_path = Path("output/dictionary_page_1_raw.txt")

MODEL = "gpt-6-astra"
MAX_OUTPUT_TOKENS = 6000


# --------------------------------------------------
# Check configuration and input
# --------------------------------------------------

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError(
        "OPENAI_API_KEY is missing. Add it to your .env file."
    )

if not image_path.exists():
    raise FileNotFoundError(
        f"Image not found: {image_path.resolve()}"
    )

json_path.parent.mkdir(parents=True, exist_ok=True)

client = OpenAI()


# --------------------------------------------------
# Encode the page image
# --------------------------------------------------

image_bytes = image_path.read_bytes()
encoded_image = base64.b64encode(image_bytes).decode("utf-8")

if image_path.suffix.lower() == ".png":
    mime_type = "image/png"
elif image_path.suffix.lower() in {".jpg", ".jpeg"}:
    mime_type = "image/jpeg"
else:
    raise ValueError("Input image must be PNG or JPEG.")


# --------------------------------------------------
# Extract dictionary entries
# --------------------------------------------------

prompt = """
Transcribe the Nupe-English dictionary page in the attached image.

Return one JSON object with:
- page_number: integer
- entries: array
- page_notes: array of strings

Each entry must have:
- headword: string
- alternative_spellings: array of strings
- senses: array of objects
- additional_information: array of strings
- source_page: integer
- source_excerpt: string
- review_required: boolean

Each sense must have:
- part_of_speech: string or null
- definition_en: string
- category_code: string or null

Rules:
- This is PDF page 5, printed dictionary page 1.
- Set page_number and source_page to 5.
- Preserve the original entry order.
- Do not include column headings as entries.
- Preserve all distinct senses and explicitly printed notes.
- Do not invent missing information.
- Preserve punctuation, apostrophes, repeated vowels,
  and the original spelling as closely as possible.
- Distinguish acute accents (á), grave accents (à),
  and carons (ǎ).
- Do not silently replace an uncertain character with a guess.
- Set review_required to true for every entry.
- If a character is unclear, explain the uncertainty in
  additional_information.
- Return valid JSON only, without Markdown fences.

Accuracy is more important than filling in uncertain details.
"""


print(f"Sending page to {MODEL}...", flush=True)

response = client.responses.create(
    model=MODEL,
    instructions=(
        "You are transcribing a historical dictionary. "
        "Do not claim uncertain text is verified."
    ),
    input=[
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {
                    "type": "input_image",
                    "image_url": (
                        f"data:{mime_type};base64,{encoded_image}"
                    ),
                    "detail": "high",
                },
            ],
        }
    ],
    max_output_tokens=MAX_OUTPUT_TOKENS,
)


# --------------------------------------------------
# Save raw response immediately
# --------------------------------------------------

raw = response.output_text or ""
raw_path.write_text(raw, encoding="utf-8")

print("Response received.", flush=True)
print(f"Response status: {response.status}", flush=True)
print(f"Raw response saved to: {raw_path}", flush=True)

if response.usage:
    print(
        f"Input tokens: {response.usage.input_tokens}",
        flush=True,
    )
    print(
        f"Output tokens: {response.usage.output_tokens}",
        flush=True,
    )

if response.status != "completed":
    raise RuntimeError(
        f"Response did not complete: {response.status}. "
        f"Inspect {raw_path}."
    )

if not raw.strip():
    raise RuntimeError(
        f"Model returned no text. Inspect {raw_path}."
    )


# --------------------------------------------------
# Parse and validate JSON
# --------------------------------------------------

try:
    data = json.loads(raw)
    result = DictionaryPage.model_validate(data)

except (json.JSONDecodeError, ValueError) as exc:
    raise ValueError(
        f"Could not parse or validate the response. "
        f"Inspect {raw_path}."
    ) from exc


# --------------------------------------------------
# Protect against empty extraction
# --------------------------------------------------

if not result.entries:
    raise ValueError(
        "No dictionary entries were extracted. "
        f"Inspect {raw_path}."
    )


# --------------------------------------------------
# Flag all entries for manual review
# --------------------------------------------------

for entry in result.entries:
    entry.review_required = True


# --------------------------------------------------
# Save structured output
# --------------------------------------------------

json_path.write_text(
    json.dumps(
        result.model_dump(),
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# --------------------------------------------------
# Report results
# --------------------------------------------------

print()
print("Extraction completed.")
print(f"Entries extracted: {len(result.entries)}")
print(f"JSON saved to: {json_path}")
print(f"Raw response saved to: {raw_path}")
print("All entries require manual verification.")
