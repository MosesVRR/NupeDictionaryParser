
import pymupdf
from pathlib import Path

pdf_path = Path("data/Nupe Dictionary_1-8.pdf")
output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

with pymupdf.open(pdf_path) as pdf:
    page = pdf[4]  # PDF page 5

    # Inspect the page dimensions first.
    print("Page dimensions:", page.rect)

    # Render at higher resolution.
    pix = page.get_pixmap(dpi=450)
    full_image = output_dir / "dictionary_page_1_450dpi.png"
    pix.save(full_image)

    print("Saved:", full_image)
    print("Open the image and identify the headword column boundaries.")
