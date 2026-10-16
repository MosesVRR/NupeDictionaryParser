
import json
from pathlib import Path

from nupe_to_eng_textprocessor.models import DictionaryEntry, DictionaryPage, Sense


entry = DictionaryEntry(
    headword="ádúwaci",
    senses=[
        Sense(
            part_of_speech="n.",
            definition_en="Desert date",
            category_code="t",
        )
    ],
    additional_information=[
        "The fruit is edible and gum is obtained from it.",
        "Balanites aegyptiaca.",
        "Hausa",
    ],
    source_pdf_page=5,
    source_printed_page=1,
    source_excerpt="ádúwaci | n. | t | Desert date",
    review_required=True,
    human_verified=False,
)

page = DictionaryPage(
    pdf_page_number=5,
    printed_page_number=1,
    entries=[entry],
)

output_path = Path("output/test_entry.json")
output_path.parent.mkdir(parents=True, exist_ok=True)

output_path.write_text(
    page.model_dump_json(indent=2),
    encoding="utf-8",
)

print(f"Saved to: {output_path}")

loaded_page = DictionaryPage.model_validate_json(
    output_path.read_text(encoding="utf-8")
)

print(f"Loaded {len(loaded_page.entries)} entry successfully.")
print(f"Headword: {loaded_page.entries[0].headword}")