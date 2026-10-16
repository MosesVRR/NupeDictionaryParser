
import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

PROMPT = """
Transcribe every Nupe headword visible in this image, in order.

Return one headword per line. Do not provide definitions,
translations, explanations, or JSON.

Preserve every character exactly, especially:
- acute accents (á)
- grave accents (à)
- carons (ǎ)
- circumflexes, apostrophes, and other marks

Do not substitute one diacritic for another.
If a character is unclear, mark it with [?].
Exclude the headings "R.M. Blench", "Nupe", and "A.".

Do not infer spelling from familiar words or context.
Transcribe only what is visibly printed.
"""


def transcribe_headwords(
    image_path: Path,
    output_path: Path,
) -> str:
    """Transcribe headwords from one cropped dictionary image."""

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing from .env.")

    if not image_path.is_file():
        raise FileNotFoundError(
            f"Image not found: {image_path.resolve()}"
        )

    suffix = image_path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }

    if suffix not in mime_types:
        raise ValueError("Image must be PNG or JPEG.")

    image_bytes = image_path.read_bytes()
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    client = OpenAI()

    print(f"Transcribing {image_path.name}...", flush=True)

    response = client.responses.create(
        model="gpt-6-astra",
        instructions=(
            "You are performing character-level transcription. "
            "Accuracy is more important than guessing."
        ),
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": PROMPT,
                    },
                    {
                        "type": "input_image",
                        "image_url": (
                            f"data:{mime_types[suffix]};"
                            f"base64,{encoded_image}"
                        ),
                        "detail": "original",
                    },
                ],
            }
        ],
        max_output_tokens=1500,
    )

    if response.status != "completed":
        raise RuntimeError(
            f"Response did not complete: {response.status}"
        )

    raw = response.output_text or ""

    if not raw.strip():
        raise RuntimeError("OpenAI returned an empty transcription.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(raw, encoding="utf-8")

    print(f"Saved transcription to: {output_path}")

    if response.usage:
        print(f"Input tokens: {response.usage.input_tokens}")
        print(f"Output tokens: {response.usage.output_tokens}")

    return raw


if __name__ == "__main__":
    image = Path("data/headword_crops/headwords_test_p3.png")
    output = Path("output/headwords_test_p3_openai.txt")

    transcription = transcribe_headwords(image, output)

    print("\n--- TRANSCRIPTION ---")
    print(transcription)
