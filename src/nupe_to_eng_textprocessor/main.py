
import base64
import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

from nupe_to_eng_textprocessor.models import DictionaryPage


load_dotenv()

image_path = Path("output/dictionary_page_1.png")
json_path = Path("output/dictionary_page_1.json")

if not image_path.exists():
    raise FileNotFoundError(f"Image not found: {image_path}")

# Read the rendered dictionary page.
image_data = base64.b64encode(image_path.read_bytes()).decode("utf-8")

# Use a vision-capable model with structured output.
llm = ChatOllama(
    model="gemma4:31b-cloud",
    base_url="https://ollama.com",
    temperature=0,
)

structured_llm = llm.with_structured_output(DictionaryPage)

message = HumanMessage(
    content=[
        {
            "type": "text",
            "text": """
Extract the dictionary entries from this scanned Nupe-English
dictionary page.

Rules:
1. Preserve Nupe headwords exactly, including tone marks,
   vowel marks, nasalization, and other diacritics.
2. Follow the page's columns: Nupe, part of speech,
   category code, English definition, and additional information.
3. Keep separate parts of speech or meanings as separate senses
   when they belong to the same headword.
4. Preserve alternative spellings, etymologies, and
   cross-references in additional_information.
5. Do not invent missing or illegible text.
6. If something is uncertain, flag the entry for review and
   explain the uncertainty in page_notes or additional_information.
7. This is PDF page 5, which is printed dictionary page 1.
   Use 5 for source_page and page_number.
8. Include all readable entries on the page.
"""
        },
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{image_data}"
            },
        },
    ]
)

result = structured_llm.invoke([message])

# Save the structured result as readable JSON.
json_path.write_text(
    json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"Extracted {len(result.entries)} entries.")
print(f"Saved results to: {json_path}")
print(json_path.read_text(encoding="utf-8"))