
from pathlib import Path
from ollama import chat

image_path = Path("output/isolated_word.png")

response = chat(
    model="gemma4:31b-cloud",
    messages=[
        {
            "role": "user",
            "content": """
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
""",
            "images": [str(image_path.resolve())],
        }
    ],
    options={"temperature": 0},
)

print(response.message.content)
