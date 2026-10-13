
import pymupdf
from pathlib import Path

pdf_path = Path("data/Nupe Dictionary_1-8.pdf")

if not pdf_path.exists():
    raise FileNotFoundError(f"PDF not found: {pdf_path}")

with pymupdf.open(pdf_path) as pdf:
    print(f"Total PDF pages: {len(pdf)}")

    # The first page containing dictionary entries
    # is PDF page 5 (index 4).
    page = pdf[4]

    output_path = Path("output")
    output_path.mkdir(exist_ok=True)

    image = page.get_pixmap(dpi=300)
    image.save(output_path / "dictionary_page_1.png")

    print("Rendered the first dictionary page.")
    print("Check output/dictionary_page_1.png")