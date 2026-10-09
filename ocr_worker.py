import json
import re
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps
import pypdfium2 as pdfium
from page_ingestion import detect_spread_split


OCR_CPU_THREADS = 2
TEXT_DETECTION_MODEL = "PP-OCRv6_medium_det"
TEXT_RECOGNITION_MODEL = "PP-OCRv6_medium_rec"


def _image_pages(path: Path, temporary_dir: Path):
    if path.suffix.lower() != ".pdf":
        with Image.open(path) as image:
            yield ImageOps.exif_transpose(image).convert("RGB")
        return
    document = pdfium.PdfDocument(str(path))
    try:
        if len(document) == 0:
            raise ValueError(f"PDF contains no pages: {path.name}")
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=2)
            yield bitmap.to_pil().convert("RGB")
    finally:
        document.close()


def _split_image(image: Image.Image, page_type: str):
    if page_type != "double" or image.width < image.height * 1.25:
        return [image]
    split_x = detect_spread_split(image)
    return [image.crop((0, 0, split_x, image.height)), image.crop((split_x, 0, image.width, image.height))]


def _expected_page_count(paths: list[Path], page_type: str) -> int:
    count = 0
    for path in paths:
        if path.suffix.lower() == ".pdf":
            document = pdfium.PdfDocument(str(path))
            try:
                for index in range(len(document)):
                    width, height = document[index].get_size()
                    count += 2 if page_type == "double" and width >= height * 1.25 else 1
            finally:
                document.close()
            continue
        with Image.open(path) as image:
            width, height = image.size
        count += 2 if page_type == "double" and width >= height * 1.25 else 1
    return count


def _ocr_image(pipeline, image: Image.Image, index: int, temporary_dir: Path) -> str:
    image_path = temporary_dir / f"page_{index:05d}.png"
    image.save(image_path)
    results = pipeline.predict(input=str(image_path))
    if not results:
        raise RuntimeError(f"PaddleOCR returned no result for page {index}.")
    result = results[0].json
    if not isinstance(result, dict):
        raise RuntimeError(f"PaddleOCR returned an invalid result for page {index}.")
    result = result.get("res", result)
    lines = result.get("rec_texts")
    if not isinstance(lines, list):
        raise RuntimeError(f"PaddleOCR returned no recognized text for page {index}.")
    text = "\n".join(line.strip() for line in lines if isinstance(line, str) and line.strip())
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    request = json.load(sys.stdin)
    paths = [Path(path) for path in request["paths"]]
    page_type = request["page_type"]
    if not paths:
        raise ValueError("No page files were supplied.")
    total_pages = _expected_page_count(paths, page_type)
    print(
        "COMBAT_AI_OCR_PROGRESS:"
        + json.dumps({"completed": 0, "total": total_pages, "phase": "initializing"}),
        flush=True,
    )
    from paddleocr import PaddleOCR

    pipeline = PaddleOCR(
        text_detection_model_name=TEXT_DETECTION_MODEL,
        text_recognition_model_name=TEXT_RECOGNITION_MODEL,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
        cpu_threads=OCR_CPU_THREADS,
    )
    sections = []
    page_number = 1
    with tempfile.TemporaryDirectory(prefix="combat-ai-ocr-") as temporary:
        temporary_dir = Path(temporary)
        for path in paths:
            try:
                for image in _image_pages(path, temporary_dir):
                    for page_image in _split_image(image, page_type):
                        text = _ocr_image(pipeline, page_image, page_number, temporary_dir)
                        if not text:
                            raise ValueError("PaddleOCR found no readable text.")
                        sections.append(f"## Page {page_number}\n\n{text}")
                        page_number += 1
                        print(
                            "COMBAT_AI_OCR_PROGRESS:"
                            + json.dumps({
                                "completed": page_number - 1,
                                "total": total_pages,
                                "phase": "ocr",
                            }),
                            flush=True,
                        )
            except Exception as error:
                raise RuntimeError(f"Could not process '{path.name}': {error}") from error
    print("COMBAT_AI_OCR_RESULT:" + json.dumps({"text": "\n\n---\n\n".join(sections)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"OCR failed: {error}", file=sys.stderr)
        raise SystemExit(1)
