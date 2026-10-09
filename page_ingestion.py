import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps

BASE_DIR = Path(__file__).resolve().parent
SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".pdf"}
OCR_PYTHON = Path(
    os.getenv("OCR_PYTHON", str(BASE_DIR / ".ocr-venv" / "Scripts" / "python.exe"))
)
OCR_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", str(4 * 60 * 60)))
if OCR_TIMEOUT_SECONDS <= 0:
    raise ValueError("OCR_TIMEOUT_SECONDS must be a positive number of seconds.")


def _timeout_message() -> str:
    timeout_minutes = OCR_TIMEOUT_SECONDS // 60
    return (
        f"PaddleOCR exceeded the {timeout_minutes}-minute processing limit. "
        "Increase OCR_TIMEOUT_SECONDS to allow longer imports."
    )


def detect_spread_split(image: Image.Image) -> int:
    width, height = image.size
    if width < height * 1.25:
        return width // 2
    gray = ImageOps.grayscale(image)
    sample = gray.resize((min(width, 1200), min(height, 500)))
    sample_width, sample_height = sample.size
    pixels = sample.load()
    densities = [
        sum(1 for y in range(sample_height) if pixels[x, y] < 210) / sample_height
        for x in range(sample_width)
    ]
    radius = max(2, sample_width // 180)
    smooth = []
    for x in range(sample_width):
        left, right = max(0, x - radius), min(sample_width, x + radius + 1)
        smooth.append(sum(densities[left:right]) / (right - left))
    start, end = int(sample_width * 0.3), int(sample_width * 0.7)
    candidate = min(range(start, end), key=smooth.__getitem__)
    side_density = sorted(smooth[int(sample_width * 0.12):int(sample_width * 0.88)])
    if not side_density:
        return width // 2
    reference = side_density[len(side_density) // 2]
    if reference < 0.025 or smooth[candidate] > reference * 0.55:
        return width // 2
    split_x = round(candidate * width / sample_width)
    return max(int(width * 0.3), min(int(width * 0.7), split_x))


def _natural_key(path: Path):
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def collect_page_files(source: str) -> list[Path]:
    path = Path(source).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Page source does not exist: {path}")
    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError("Choose a supported image or PDF file.")
        return [path]
    if not path.is_dir():
        raise ValueError("Page source must be a file or folder.")
    paths = sorted(
        (
            entry
            for entry in path.rglob("*")
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_SUFFIXES
        ),
        key=_natural_key,
    )
    if not paths:
        raise ValueError("The selected folder contains no supported images or PDFs.")
    return paths


def _run_ocr_worker_with_progress(payload: dict, progress_callback: Callable[[int, int], None]) -> str:
    command = [str(OCR_PYTHON), "-u", str(BASE_DIR / "ocr_worker.py")]
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as error:
        raise RuntimeError(f"Could not start PaddleOCR worker: {error}") from error
    if process.stdin is None or process.stdout is None:
        process.kill()
        raise RuntimeError("Could not connect to PaddleOCR worker output.")

    output_lines: list[str] = []
    output_queue: queue.Queue[str | None] = queue.Queue()

    def read_output() -> None:
        try:
            for line in process.stdout:
                output_queue.put(line)
        finally:
            output_queue.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    try:
        process.stdin.write(json.dumps(payload))
        process.stdin.close()
        deadline = time.monotonic() + OCR_TIMEOUT_SECONDS
        reader_finished = False
        while not reader_finished:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                raise RuntimeError(_timeout_message())
            try:
                line = output_queue.get(timeout=min(0.25, remaining))
            except queue.Empty:
                if process.poll() is not None and not reader.is_alive():
                    break
                continue
            if line is None:
                reader_finished = True
                continue
            if line.startswith("COMBAT_AI_OCR_PROGRESS:"):
                try:
                    progress = json.loads(line.removeprefix("COMBAT_AI_OCR_PROGRESS:"))
                    completed = int(progress["completed"])
                    total = int(progress["total"])
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    output_lines.append(line)
                    continue
                progress_callback(completed, total)
            else:
                output_lines.append(line)
        return_code = process.wait(timeout=5)
    except Exception:
        if process.poll() is None:
            process.kill()
            process.wait()
        raise
    finally:
        reader.join(timeout=5)

    stdout = "".join(output_lines)
    if return_code:
        detail = stdout.strip() or "OCR worker failed."
        raise RuntimeError(detail[-4000:])
    result_lines = [
        line.removeprefix("COMBAT_AI_OCR_RESULT:")
        for line in output_lines
        if line.startswith("COMBAT_AI_OCR_RESULT:")
    ]
    if not result_lines:
        raise RuntimeError("OCR worker returned no result marker.")
    try:
        response = json.loads(result_lines[-1])
    except json.JSONDecodeError as error:
        raise RuntimeError(f"OCR worker returned invalid output: {error}") from error
    if not isinstance(response, dict) or not isinstance(response.get("text"), str):
        raise RuntimeError("OCR worker returned no extracted text.")
    return response["text"].strip()


def extract_pages(
    paths: list[Path],
    page_type: str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> str:
    if page_type not in {"single", "double"}:
        raise ValueError("Page type must be single or double.")
    if not OCR_PYTHON.is_file():
        raise RuntimeError(
            f"PaddleOCR runtime was not found at {OCR_PYTHON}. Set OCR_PYTHON to the installed OCR Python executable."
        )
    payload = {"paths": [str(path) for path in paths], "page_type": page_type}
    if progress_callback is not None:
        text = _run_ocr_worker_with_progress(payload, progress_callback)
        if not text:
            raise ValueError("OCR completed, but no readable text was found.")
        return text
    try:
        result = subprocess.run(
            [str(OCR_PYTHON), str(BASE_DIR / "ocr_worker.py")],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=OCR_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(_timeout_message()) from error
    stdout = result.stdout if isinstance(result.stdout, str) else ""
    stderr = result.stderr if isinstance(result.stderr, str) else ""
    if result.returncode:
        detail = stderr.strip() or stdout.strip() or "OCR worker failed."
        raise RuntimeError(detail[-4000:])
    output_lines = [
        line.removeprefix("COMBAT_AI_OCR_RESULT:")
        for line in stdout.splitlines()
        if line.startswith("COMBAT_AI_OCR_RESULT:")
    ]
    if not output_lines:
        raise RuntimeError("OCR worker returned no result marker.")
    try:
        response = json.loads(output_lines[-1])
    except json.JSONDecodeError as error:
        raise RuntimeError(f"OCR worker returned invalid output: {error}") from error
    if not isinstance(response, dict) or not isinstance(response.get("text"), str):
        raise RuntimeError("OCR worker returned no extracted text.")
    text = response["text"].strip()
    if not text:
        raise ValueError("OCR completed, but no readable text was found.")
    return text
