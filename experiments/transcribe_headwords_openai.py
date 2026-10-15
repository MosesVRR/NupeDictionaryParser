
import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# Load the API key from your project's .env file.
load_dotenv()

image_path = Path("output/headwords_test_p2.png")
raw_path = Path("output/headwords_test_p2_openai.txt")

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError(
        "OPENAI_API_KEY is missing from your .env file."
    )

if not image_path.exists():
    raise FileNotFoundError(
        f"Image not found: {image_path.resolve()}"
    )

# Read and encode the image.
image_bytes = image_path.read_bytes()
encoded_image = base64.b64encode(image_bytes).decode("utf-8")

suffix = image_path.suffix.lower()

if suffix == ".png":
    mime_type = "image/png"
elif suffix in {".jpg", ".jpeg"}:
    mime_type = "image/jpeg"
else:
    raise ValueError("Image must be PNG or JPEG.")

client = OpenAI()

prompt = """
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

print("Sending image to OpenAI...", flush=True)

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
                    "text": prompt,
                },
                {
                    "type": "input_image",
                    "image_url": (
                        f"data:{mime_type};base64,{encoded_image}"
                    ),
                    "detail": "original",
                },
            ],
        }
    ],
    max_output_tokens=1500,
)

raw = response.output_text or ""

# Save the exact returned text for comparison.
raw_path.parent.mkdir(parents=True, exist_ok=True)
raw_path.write_text(raw, encoding="utf-8")

print(f"Response status: {response.status}")
print(f"Transcription saved to: {raw_path}")

if response.usage:
    print(f"Input tokens: {response.usage.input_tokens}")
    print(f"Output tokens: {response.usage.output_tokens}")

if response.status != "completed":
    raise RuntimeError(
        f"Response did not complete: {response.status}"
    )

if not raw.strip():
    raise RuntimeError("OpenAI returned an empty transcription.")

print("\n--- TRANSCRIPTION ---")
print(raw)
