
from pathlib import Path
from paddleocr import PaddleOCR

image_path = Path("output/headwords_test.png")

if not image_path.exists():
    raise FileNotFoundError(
        f"Image not found: {image_path.resolve()}"
    )

print("Initializing PaddleOCR...", flush=True)

ocr = PaddleOCR(
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    engine="paddle",
)

print("Running OCR...", flush=True)

results = ocr.predict(str(image_path.resolve()))

print("\n--- PADDLEOCR OUTPUT ---\n")

print("\n--- PADDLEOCR HEADWORDS ---\n")

for result in results:
    data = result.json
    if callable(data):
        data = data()

    # PaddleOCR may wrap the prediction in a "res" object.
    data = data.get("res", data)

    texts = data.get("rec_texts", [])
    scores = data.get("rec_scores", [])

    for i, text in enumerate(texts):
        score = float(scores[i]) if i < len(scores) else 0.0
        print(f"{i + 1:02d}. {text:<25} confidence={score:.3f}")
