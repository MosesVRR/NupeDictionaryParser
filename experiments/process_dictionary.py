import base64
import json
import logging
import os
from pathlib import Path

import pymupdf  # PyMuPDF
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from nupe_to_eng_textprocessor.models import DictionaryEntry, DictionaryPage


# Run this script from the project root.
PDF_PATH = Path("data/Nupe Dictionary_5-208.pdf")

IMAGE_DIR = Path("output/pages")
RAW_DIR = Path("output/raw")
PAGE_DIR = Path("output/validated")
LOG_DIR = Path("output/logs")

DPI = 450
MODEL = "gpt-6-astra"

# The reduced PDF begins at original PDF page 5, which is printed page 1.
ORIGINAL_PDF_PAGE_OFFSET = 4

# Optional: set to integers to process only a range of reduced-PDF pages.
# These are 1-based page numbers in the REDUCED PDF.
START_PAGE = 1
END_PAGE = None  # None means through the final page.


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

PAGE BOUNDARIES:
- If text at the top or bottom of a page appears to continue an entry
  from an adjacent page, record that observation in page_notes.
- Do not invent the missing portion or silently merge entries across
  pages. Preserve what is visible on this page.

Return JSON only. Do not use Markdown code fences or explanations.
"""


def page_paths(reduced_page_number: int) -> tuple[Path, Path, Path]:
    stem = f"page_{reduced_page_number:03d}"
    return (
        IMAGE_DIR / f"{stem}_{DPI}dpi.png",
        RAW_DIR / f"{stem}_raw.json",
        PAGE_DIR / f"{stem}_validated.json",
    )


def render_page(pdf_document: pymupdf.Document, reduced_page_number: int) -> Path:
    """Render a 1-based page of the reduced PDF to a PNG."""
    image_path, _, _ = page_paths(reduced_page_number)
    image_path.parent.mkdir(parents=True, exist_ok=True)

    # PyMuPDF page indexes are zero-based. Use a DPI-based scale matrix.
    page = pdf_document.load_page(reduced_page_number - 1)
    scale = DPI / 72
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(scale, scale),
        alpha=False,
    )
    pixmap.save(image_path)
    return image_path


def extract_page(
    client: OpenAI,
    image_path: Path,
    reduced_page_number: int,
) -> tuple[str, dict]:
    """Send one rendered page to the model and return raw text and parsed JSON."""
    suffix = image_path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    if suffix not in mime_types:
        raise ValueError(f"Unsupported image type: {suffix}")

    encoded_image = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    response = client.responses.create(
        model=MODEL,
        instructions=(
            "You are transcribing a historical bilingual dictionary. "
            "Prioritize faithful transcription over guessing. Preserve Unicode "
            "characters, entry boundaries, and the distinction between section "
            "markers and headwords. Do not infer text outside the visible page."
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
        max_output_tokens=12000,
    )

    if response.status != "completed":
        raise RuntimeError(f"API response did not complete: {response.status}")

    raw = response.output_text or ""
    if not raw.strip():
        raise RuntimeError("OpenAI returned an empty response.")

    # Save raw output before parsing so a malformed response is not lost.
    _, raw_path, _ = page_paths(reduced_page_number)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw, encoding="utf-8")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Model returned invalid JSON; raw response saved to {raw_path}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object at the top level.")
    if not isinstance(data.get("entries"), list):
        raise ValueError("The response must contain an entries list.")
    if not isinstance(data.get("page_notes", []), list):
        raise ValueError("page_notes must be a list.")

    return raw, data


def validate_page(data: dict, reduced_page_number: int) -> DictionaryPage:
    """Attach page provenance locally and validate all extracted entries."""
    original_pdf_page = reduced_page_number + ORIGINAL_PDF_PAGE_OFFSET
    printed_page_number = reduced_page_number

    entries = []
    for item in data["entries"]:
        if not isinstance(item, dict):
            raise ValueError("Each item in entries must be a JSON object.")

        item = dict(item)
        item["source_pdf_page"] = original_pdf_page
        item["source_printed_page"] = printed_page_number
        item["review_required"] = True
        item["human_verified"] = False
        entries.append(DictionaryEntry.model_validate(item))

    return DictionaryPage(
        pdf_page_number=original_pdf_page,
        printed_page_number=printed_page_number,
        entries=entries,
        page_notes=data.get("page_notes", []),
    )


def existing_result_is_valid(path: Path, expected_original_page: int) -> bool:
    """Only skip a page when a saved validated file can be loaded successfully."""
    if not path.is_file():
        return False

    try:
        saved_page = DictionaryPage.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        return saved_page.pdf_page_number == expected_original_page
    except (ValidationError, ValueError, OSError):
        return False


def save_validated_page(page: DictionaryPage, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page.model_dump_json(indent=2), encoding="utf-8")


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing from the project's .env file.")
    if not PDF_PATH.is_file():
        raise FileNotFoundError(
            f"PDF not found: {PDF_PATH.resolve()}\n"
            "Update PDF_PATH at the top of this script to match your filename/location."
        )

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_DIR / "processing.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )

    client = OpenAI()
    successes = 0
    skipped = 0
    failures = 0

    with pymupdf.open(PDF_PATH) as pdf_document:
        total_pages = len(pdf_document)
        start_page = max(1, START_PAGE)
        end_page = min(END_PAGE or total_pages, total_pages)

        if start_page > end_page:
            raise ValueError(
                f"Invalid page range: START_PAGE={start_page}, END_PAGE={end_page}"
            )

        print(f"PDF: {PDF_PATH}")
        print(f"Pages in reduced PDF: {total_pages}")
        print(f"Processing reduced-PDF pages {start_page} through {end_page}")
        print(f"Rendering at {DPI} DPI with model {MODEL}\n")

        for reduced_page_number in range(start_page, end_page + 1):
            original_pdf_page = reduced_page_number + ORIGINAL_PDF_PAGE_OFFSET
            image_path, raw_path, validated_path = page_paths(reduced_page_number)

            if existing_result_is_valid(validated_path, original_pdf_page):
                print(
                    f"[SKIP] Reduced page {reduced_page_number}: "
                    f"validated output already exists."
                )
                skipped += 1
                continue

            print(
                f"[START] Reduced page {reduced_page_number}/{total_pages} "
                f"(original PDF page {original_pdf_page}, "
                f"printed page {reduced_page_number})",
                flush=True,
            )

            try:
                render_page(pdf_document, reduced_page_number)
                _, data = extract_page(client, image_path, reduced_page_number)
                page = validate_page(data, reduced_page_number)
                save_validated_page(page, validated_path)

                print(
                    f"[OK] {len(page.entries)} entries -> {validated_path}",
                    flush=True,
                )
                successes += 1
                logging.info(
                    "SUCCESS reduced_page=%s original_pdf_page=%s entries=%s "
                    "image=%s raw=%s validated=%s",
                    reduced_page_number,
                    original_pdf_page,
                    len(page.entries),
                    image_path,
                    raw_path,
                    validated_path,
                )

            except Exception as exc:
                failures += 1
                print(
                    f"[FAILED] Reduced page {reduced_page_number}: {exc}",
                    flush=True,
                )
                logging.exception(
                    "FAILED reduced_page=%s original_pdf_page=%s",
                    reduced_page_number,
                    original_pdf_page,
                )
                # Continue to the next page; retry failed pages on a later run.

    print("\n--- SUMMARY ---")
    print(f"Successfully processed this run: {successes}")
    print(f"Skipped (already validated): {skipped}")
    print(f"Failed: {failures}")
    print(f"Logs: {LOG_DIR / 'processing.log'}")


if __name__ == "__main__":
    main()
