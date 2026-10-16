import re
from pathlib import Path

from transcribe_headwords import transcribe_headwords


INPUT_DIR = Path("data/headword_crops")
OUTPUT_DIR = Path("output/headwords")


def main():
    images = sorted(
        (
            path
            for path in INPUT_DIR.glob("headwords_test_p*.png")
            if re.fullmatch(r"headwords_test_p\d+\.png", path.name)
        ),
        key=lambda path: int(
            re.search(r"p(\d+)\.png$", path.name).group(1)
        ),
    )

    if not images:
        print(f"No cropped images found in {INPUT_DIR.resolve()}")
        return

    print(f"Found {len(images)} images.")

    for image_path in images:
        output_path = OUTPUT_DIR / f"{image_path.stem}_openai.txt"

        if output_path.exists():
            print(f"Skipping existing transcription: {output_path}")
            continue

        try:
            transcribe_headwords(image_path, output_path)
        except Exception as exc:
            print(f"FAILED: {image_path.name}: {exc}")
            continue

    print("Batch processing finished.")


if __name__ == "__main__":
    main()
