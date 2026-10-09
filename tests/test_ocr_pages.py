import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw

import page_ingestion
from ocr_processor import split_spread, spread_page_number
from page_ingestion import detect_spread_split, extract_pages


class OcrPageTests(unittest.TestCase):
    def test_spread_is_split_into_separate_left_and_right_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "spread.png"
            image = Image.new("RGB", (101, 20), "white")
            image.paste("red", (0, 0, 50, 20))
            image.paste("blue", (50, 0, 101, 20))
            image.save(image_path)

            pages = split_spread(image_path, 6)

        self.assertEqual([number for number, _ in pages], [6, 7])
        self.assertEqual([page.width for _, page in pages], [50, 51])
        self.assertEqual(pages[0][1].getpixel((10, 10)), (255, 0, 0))
        self.assertEqual(pages[1][1].getpixel((10, 10)), (0, 0, 255))

    def test_spread_filename_controls_the_printed_page_numbers(self):
        self.assertEqual(spread_page_number(Path("page_006_007.jpg"), 1), 6)
        self.assertEqual(spread_page_number(Path("page_040_041 .jpg"), 1), 40)

    def test_nonconsecutive_spread_filename_is_rejected(self):
        with self.assertRaises(ValueError):
            spread_page_number(Path("page_006_008.jpg"), 1)

    def test_spread_detection_uses_the_content_gutter_instead_of_fixed_midpoint(self):
        image = Image.new("RGB", (1000, 500), "white")
        draw = ImageDraw.Draw(image)
        for y in range(30, 480, 18):
            draw.line((45, y, 400, y), fill="black", width=3)
            draw.line((470, y, 950, y), fill="black", width=3)

        split_x = detect_spread_split(image)

        self.assertGreater(split_x, 380)
        self.assertLess(split_x, 470)

    def test_extract_pages_replaces_invalid_utf8_and_preserves_worker_text(self):
        result = SimpleNamespace(
            returncode=0,
            stdout='COMBAT_AI_OCR_RESULT:{"text":"détente"}\n',
            stderr="",
        )
        with (
            patch("page_ingestion.OCR_PYTHON", Path(__file__)),
            patch("page_ingestion.subprocess.run", return_value=result) as run,
        ):
            text = extract_pages([Path("page.png")], "single")

        self.assertEqual(text, "détente")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")
        self.assertEqual(run.call_args.kwargs["timeout"], page_ingestion.OCR_TIMEOUT_SECONDS)

    def test_extract_pages_handles_missing_stdout_without_calling_splitlines(self):
        result = SimpleNamespace(returncode=0, stdout=None, stderr=None)
        with (
            patch("page_ingestion.OCR_PYTHON", Path(__file__)),
            patch("page_ingestion.subprocess.run", return_value=result),
        ):
            with self.assertRaisesRegex(RuntimeError, "returned no result marker"):
                extract_pages([Path("page.png")], "single")

    def test_extract_pages_streams_worker_page_progress(self):
        response = {"text": "## Page 1\n\nPage text"}
        stdout = (
            "COMBAT_AI_OCR_PROGRESS:"
            + json.dumps({"completed": 1, "total": 2, "phase": "ocr"})
            + "\nCOMBAT_AI_OCR_RESULT:"
            + json.dumps(response, ensure_ascii=False)
            + "\n"
        )

        class FakeProcess:
            def __init__(self):
                self.stdin = io.StringIO()
                self.stdout = io.StringIO(stdout)
                self.returncode = 0

            def poll(self):
                return 0

            def wait(self, timeout=None):
                return 0

            def kill(self):
                self.returncode = -1

        updates = []
        with (
            patch("page_ingestion.OCR_PYTHON", Path(__file__)),
            patch("page_ingestion.subprocess.Popen", return_value=FakeProcess()),
        ):
            text = extract_pages(
                [Path("page.png")],
                "single",
                progress_callback=lambda completed, total: updates.append((completed, total)),
            )

        self.assertEqual(text, response["text"])
        self.assertEqual(updates, [(1, 2)])

    def test_ocr_timeout_is_configured_for_long_imports(self):
        self.assertGreaterEqual(page_ingestion.OCR_TIMEOUT_SECONDS, 4 * 60 * 60)

    def test_timeout_error_reports_the_configured_limit(self):
        with (
            patch("page_ingestion.OCR_PYTHON", Path(__file__)),
            patch(
                "page_ingestion.subprocess.run",
                side_effect=subprocess.TimeoutExpired("ocr", 1),
            ),
            patch.object(page_ingestion, "OCR_TIMEOUT_SECONDS", 120),
        ):
            with self.assertRaisesRegex(RuntimeError, "2-minute processing limit"):
                extract_pages([Path("page.png")], "single")


if __name__ == "__main__":
    unittest.main()
