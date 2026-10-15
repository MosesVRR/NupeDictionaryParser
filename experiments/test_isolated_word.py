
from pathlib import Path
from ollama import chat

image_path = Path("output/isolated_word.png")

if not image_path.exists():
    raise FileNotFoundError(f"Image not found: {image_path}")

print("Sending isolated word to Gemma 4 31B Cloud...", flush=True)

response = chat(
    model="gemma4:31b-cloud",
    messages=[
        {
            "role": "user",
            "content": """
Transcribe the Nupe headword in this image exactly as printed.

Pay particular attention to the third and fifth vowel in the sequence of letters. The source spelling is expected to contain a character with a breve below or above the letter only if that is visibly printed; do not infer the mark from the word's expected spelling.

Distinguish carefully between:
- `à` — a with a grave accent
- `ằ` — a with a grave accent and breve
- `ǎ` — a with a caron

Do not substitute one character for another. Return only the complete headword. If the mark cannot be identified confidently, return `[uncertain]` for the affected character.
""",
            "images": [str(image_path.resolve())],
        }
    ],
    options={"temperature": 0},
)

print("\n--- MODEL RESPONSE ---\n")
print(response.message.content)
