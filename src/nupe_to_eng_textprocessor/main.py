
import json
from pathlib import Path

from ollama import chat
from nupe_to_eng_textprocessor.models import DictionaryPage


image_path = Path("output/dictionary_page_1.png")
json_path = Path("output/dictionary_page_1.json")

if not image_path.exists():
    raise FileNotFoundError(f"Image not found: {image_path}")

print("Sending page to Gemma...", flush=True)

response = chat(
    model="gemma4:e4b",
    messages=[
        {
            "role": "user",
            "content": 
"""
Extract only the FIRST FIVE dictionary entries from this page.

Return one valid JSON object with these fields:
- page_number: integer
- entries: array
- page_notes: array of strings

Each entry:
- headword: string
- alternative_spellings: array of strings
- senses: array of objects
- additional_information: array of strings
- source_page: integer
- source_excerpt: string
- review_required: boolean

Each sense:
- part_of_speech: string or null
- definition_en: string
- category_code: string or null

Preserve Nupe spelling and tone marks exactly.
Do not include column headings as entries.
Do not invent information.
Set page_number and source_page to 5.
Use empty arrays when there is no additional information.
Return valid JSON only, with no Markdown fences.
""",
            "images": [str(image_path.resolve())],
        }
    ],
    format="json",
    options={"temperature": 0},
)

raw = response.message.content
print("Gemma returned a response.", flush=True)

try:
    data = json.loads(raw)
    result = DictionaryPage.model_validate(data)
except Exception:
    # Save the raw response so we can inspect any formatting problems.
    Path("output/raw_response.txt").write_text(raw, encoding="utf-8")
    raise

json_path.write_text(
    json.dumps(
        result.model_dump(),
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)

print(f"Entries extracted: {len(result.entries)}")
print(f"Saved to: {json_path}")

if not result.entries:
    print("WARNING: No entries extracted. Inspect the raw response.")
