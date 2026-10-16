
import json
from pathlib import Path

from nupe_to_eng_textprocessor.models import DictionaryEntry, DictionaryPage, Sense


entries = [
    DictionaryEntry(
        headword="àlàmu",
        senses=[
            Sense(
                part_of_speech="n.",
                definition_en="Idea; suspicion;",
            )
        ],
        source_pdf_page=5,
        source_printed_page=1,
        source_excerpt="àlàmu | n. | Idea; suspicion;",
        review_required=True,
        human_verified=False,
    ),
    DictionaryEntry(
        headword="àlàšàngì",
        senses=[
            Sense(
                part_of_speech="n.",
                definition_en="Swamp grass.",
                category_code="g",
            )
        ],
        source_pdf_page=5,
        source_printed_page=1,
        source_excerpt="àlàšàngì | n. | g | Swamp grass.",
        review_required=True,
        human_verified=False,
    ),
    DictionaryEntry(
        headword="àlàǯì",
        senses=[
            Sense(
                part_of_speech="n.",
                definition_en=(
                    "One who has performed the pilgrimage to Mecca, "
                    "and on that account dresses in white;"
                ),
            )
        ],
        additional_information=[
            "whence applied as an adjective to white animals",
            "Cross-reference: dòkò àlàǯì; cf. alaháji.",
        ],
        source_pdf_page=5,
        source_printed_page=1,
        source_excerpt="Transcribed from the supplied cropped image.",
        review_required=True,
        human_verified=False,
    ),
]

page = DictionaryPage(
    pdf_page_number=5,
    printed_page_number=1,
    entries=entries,
)

output_path = Path("output/sample_entries.json")
output_path.parent.mkdir(parents=True, exist_ok=True)

output_path.write_text(
    page.model_dump_json(indent=2),
    encoding="utf-8",
)

# Read the file back and validate it.
loaded_page = DictionaryPage.model_validate_json(
    output_path.read_text(encoding="utf-8")
)

print(f"Saved: {output_path}")
print(f"Entries loaded: {len(loaded_page.entries)}")

for entry in loaded_page.entries:
    print(f"- {entry.headword}")

print("Validation successful.")
