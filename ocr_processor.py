from pathlib import Path
import re

from PIL import Image
from page_ingestion import detect_spread_split

BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / "book_images"
OUTPUT_DIR = BASE_DIR / "dataset" / "ocr_pages"
OUTPUT_FILE = BASE_DIR / "dataset" / "pages_layout.txt"


def split_spread(image_path: Path, page_number: int):
    with Image.open(image_path) as image:
        midpoint = detect_spread_split(image)
        left = image.crop((0, 0, midpoint, image.height))
        right = image.crop((midpoint, 0, image.width, image.height))
    return [(page_number, left), (page_number + 1, right)]


def markdown_for_page(pipeline, page_image: Image.Image, page_number: int) -> str:
    page_path = OUTPUT_DIR / f"page_{page_number:04d}.png"
    page_image.save(page_path)
    results = iter(pipeline.predict(input=str(page_path)))
    result = next(results, None)
    if result is None:
        raise RuntimeError(f"PaddleOCR returned no result for page {page_number}.")

    reading_order_image = result.img.get("layout_order_res")
    if reading_order_image is not None:
        reading_order_image.save(OUTPUT_DIR / f"page_{page_number:04d}_reading_order.png")

    markdown_path = OUTPUT_DIR / f"page_{page_number:04d}.md"
    # PaddleOCR serializes its layout-detected blocks in spatial reading order,
    # including column order; avoid flattening OCR boxes into a left-to-right string.
    result.save_to_markdown(save_path=str(markdown_path))
    return markdown_path.read_text(encoding="utf-8", errors="replace").strip()


def spread_page_number(image_path: Path, fallback: int) -> int:
    match = re.search(r"page_(\d+)_(\d+)", image_path.stem, flags=re.IGNORECASE)
    if not match:
        return fallback
    first, second = (int(value) for value in match.groups())
    if second != first + 1:
        raise ValueError(f"Expected consecutive page numbers in image name: {image_path.name}")
    return first


def process_book():
    from paddleocr import PPStructureV3

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image_paths = sorted(
        (path for path in IMAGE_DIR.iterdir() if path.suffix.lower() in {".jpg", ".jpeg"}),
        key=lambda path: (spread_page_number(path, 0), path.name.lower()),
    )
    if not image_paths:
        raise FileNotFoundError(f"No JPEG book spreads found in {IMAGE_DIR}.")

    pipeline = PPStructureV3(lang="en")
    pages = []

    next_fallback_page = 1
    for image_path in image_paths:
        first_page = spread_page_number(image_path, next_fallback_page)
        print(f"Processing {image_path.name}")
        for page_number, page_image in split_spread(image_path, first_page):
            text = markdown_for_page(pipeline, page_image, page_number)
            pages.append(f"## Page {page_number}\n\n{text}")
        next_fallback_page = first_page + 2

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text("\n\n---\n\n".join(pages) + "\n", encoding="utf-8")
    print(f"Wrote layout-aware OCR to {OUTPUT_FILE}")


if __name__ == "__main__":
    process_book()
