
from pathlib import Path
import subprocess

image_path = Path("headwords_test.png")

if not image_path.exists():
    raise FileNotFoundError(f"Image not found: {image_path.resolve()}")

result = subprocess.run(
    [
        "tesseract",
        str(image_path.resolve()),
        "stdout",
        "-l", "eng",
        "--psm", "6",
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=True,
)

print("--- TESSERACT OUTPUT ---")
print(result.stdout)