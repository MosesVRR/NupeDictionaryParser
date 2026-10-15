
import json
from pathlib import Path

from ollama import chat
from nupe_to_eng_textprocessor.models import DictionaryPage


# --------------------------------------------------
# File paths
# --------------------------------------------------

image_path = Path("output/dictionary_page_1.png")
json_path = Path("output/dictionary_page_1.json")
raw_path = Path("output/dictionary_page_1_raw.txt")


# --------------------------------------------------
# Check that the input image exists
# --------------------------------------------------

if not image_path.exists():
    raise FileNotFoundError(
        f"Image not found: {image_path.resolve()}"
    )

# Ensure the output directory exists.
json_path.parent.mkdir(parents=True, exist_ok=True)

print("Sending page to Gemma...", flush=True)


# --------------------------------------------------
# Extract dictionary entries using Gemma
# --------------------------------------------------

response = chat(
    model="gemma4:31b-cloud",
    messages=[
        {
            "role": "user",
            "content": """
Extract the dictionary entries from this scanned page.

Return one valid JSON object with these fields:
- page_number: integer
- entries: array
- page_notes: array of strings

Each entry must contain:
- headword: string
- alternative_spellings: array of strings
- senses: array of objects
- additional_information: array of strings
- source_page: integer
- source_excerpt: string
- review_required: boolean

Each sense must contain:
- part_of_speech: string or null
- definition_en: string
- category_code: string or null

EXTRACTION RULES:

1. Extract the dictionary entries visible on the page.
2. Do not include column headings or page headers as entries.
3. Do not invent missing information.
4. Preserve the original order of the entries.
5. Preserve the English definitions and any available grammatical
   labels, category codes, and additional information.
6. Keep separate senses together under their corresponding
   headword.
7. Preserve alternative spellings and cross-references when
   they are explicitly printed.
8. Use empty arrays when no additional information is present.
9. Set page_number and source_page to 5, because this is PDF
   page 5. The printed dictionary page number is 1.
10. Set review_required to true for every entry.

DIACRITIC PRESERVATION — CRITICAL:

- Copy every Nupe headword as accurately as possible from the scan.
- Distinguish acute accents: á, é, í, ó, ú.
- Distinguish grave accents: à, è, ì, ò, ù.
- Preserve carons: ǎ, ě, ǐ, ǒ, ǔ.
- Do not substitute a caron with an acute accent, grave accent,
  circumflex, tilde, or plain letter.
- Preserve doubled vowels, nasalization marks, apostrophes,
  and all other printed symbols.
- Do not assume similar-looking words have identical spellings.
- If a character or diacritic is unclear, do not silently guess.
  Set review_required to true and describe the uncertainty in
  additional_information.
- Successful transcription does not mean an entry is verified.

SOURCE EXCERPT:

For each entry, include a short source_excerpt copied from
the visible scan to help locate and verify the entry later.

OUTPUT:

Return valid JSON only, without Markdown fences or commentary.
""",
            "images": [str(image_path.resolve())],
        }
    ],
    format="json",
    options={"temperature": 0},
)


# --------------------------------------------------
# Save the raw response before parsing
# --------------------------------------------------

raw = response.message.content

raw_path.write_text(raw, encoding="utf-8")

print(f"Gemma returned a response.", flush=True)
print(f"Raw response saved to: {raw_path}", flush=True)


# --------------------------------------------------
# Parse and validate the response
# --------------------------------------------------

try:
    data = json.loads(raw)
    result = DictionaryPage.model_validate(data)

except (json.JSONDecodeError, ValueError) as exc:
    raise ValueError(
        f"Could not parse or validate Gemma's response. "
        f"Inspect: {raw_path}"
    ) from exc


# --------------------------------------------------
# Protect against empty extraction
# --------------------------------------------------

if not result.entries:
    raise ValueError(
        "Gemma extracted zero entries. "
        "The output JSON was not written. "
        f"Inspect the raw response at: {raw_path}"
    )


# --------------------------------------------------
# Flag all entries for manual review
# --------------------------------------------------

for entry in result.entries:
    entry.review_required = True


# --------------------------------------------------
# Write the structured JSON output
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
print(f"PDF page number: {result.page_number}")
print(f"JSON saved to: {json_path}")
print(f"Raw response saved to: {raw_path}")
print("All entries are flagged for manual review.")
