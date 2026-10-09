import os
import re
from pathlib import Path

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
BOOK_TEXT_PATH = BASE_DIR / "extracted_book_text.txt"
OCR_TEXT_PATH = DATASET_DIR / "combat_aircraft_layout.txt"
VECTOR_DB_PATH = Path(os.getenv("VECTOR_DB_PATH", str(BASE_DIR / "aircraft_vector_db_clean")))
COLLECTION_NAME = "combat_aircraft"

PAGE_MARKER = re.compile(
    r"(?im)^\s*(?:---\s*PAGE\s+(\d+)\s*---|##\s*Page\s+(\d+)\s*)\s*$"
)
WORDS_PER_CHUNK = 120
CHUNK_OVERLAP = 24


def parse_pages(text: str) -> dict[int, str]:
    markers = list(PAGE_MARKER.finditer(text))
    if not markers:
        return {1: text.strip()} if text.strip() else {}

    pages = {}
    for index, marker in enumerate(markers):
        page_number = int(marker.group(1) or marker.group(2))
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        page_text = text[marker.end():end].strip()
        if page_text:
            pages[page_number] = page_text
    return pages


def load_book_pages() -> dict[int, str]:
    pages = {}
    if BOOK_TEXT_PATH.is_file():
        pages.update(parse_pages(BOOK_TEXT_PATH.read_text(encoding="utf-8", errors="replace")))
    if OCR_TEXT_PATH.is_file():
        ocr_pages = parse_pages(OCR_TEXT_PATH.read_text(encoding="utf-8", errors="replace"))
        pages.update(ocr_pages)
    if not pages:
        raise FileNotFoundError(
            f"No book text found. Run OCR on book_images or provide {BOOK_TEXT_PATH}."
        )
    return pages


def chunk_pages(pages: dict[int, str]) -> list[tuple[str, str, dict[str, int | str]]]:
    chunks = []
    for page_number, text in sorted(pages.items()):
        words = text.split()
        if not words:
            continue
        start = 0
        chunk_number = 0
        while start < len(words):
            end = min(start + WORDS_PER_CHUNK, len(words))
            chunk = " ".join(words[start:end]).strip()
            if chunk:
                chunks.append(
                    (
                        f"page_{page_number:04d}_chunk_{chunk_number:02d}",
                        chunk,
                        {"page": page_number, "source": "book"},
                    )
                )
            if end == len(words):
                break
            start = end - CHUNK_OVERLAP
            chunk_number += 1
    return chunks


def local_embedding_function() -> DefaultEmbeddingFunction:
    return DefaultEmbeddingFunction()
