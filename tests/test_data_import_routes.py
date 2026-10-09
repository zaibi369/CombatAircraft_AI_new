import unittest
import threading
import time
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import dataset_registry
import server


class DatasetImportRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)

    def test_online_text_validates_api_records_and_registers_metadata(self):
        response = Mock()
        response.headers = {"content-type": "application/json"}
        response.text = '{"documents":[{"title":"Chapter One","content":"Grounded source evidence."}]}'
        response.json.return_value = {
            "documents": [{"title": "Chapter One", "content": "Grounded source evidence."}]
        }
        stored = {
            "dataset_id": "data_api_text",
            "dataset_name": "Chapter_One",
            "source": "https://api.example.test/documents",
            "scope": "api",
            "type": "text",
            "origin": "api_text",
            "scenario": "Reference work",
            "created_at": "2026-01-01T00:00:00+00:00",
            "embedding_model": "all-MiniLM-L6-v2",
            "api_name": "Chapter One API",
            "endpoint": "https://api.example.test/documents",
            "items": 1,
        }
        with (
            patch.object(server, "_online_response", return_value=response) as fetch,
            patch.object(server, "store_text_dataset", return_value=stored) as store,
        ):
            result = self.client.post(
                "/datasets/import/text",
                json={
                    "source_type": "ONLINE_API",
                    "source_url": "https://api.example.test/documents",
                    "api_key": "test-token",
                    "scenario": "Reference work",
                },
            )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["name"], stored["dataset_name"])
        self.assertEqual(result.json()["source_type"], "ONLINE_API")
        self.assertEqual(result.json()["data_type"], "TEXT")
        self.assertIn("retrieval_metadata", result.json())
        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.args[0], "https://api.example.test/documents")
        self.assertEqual(fetch.call_args.args[1], "test-token")
        self.assertEqual(store.call_args.kwargs["text"], "Chapter One\nGrounded source evidence.")
        self.assertEqual(store.call_args.kwargs["data_type"], "TEXT")
        self.assertEqual(store.call_args.kwargs["source_type"], "ONLINE_API")
        self.assertEqual(store.call_args.kwargs["scenario"], "Reference work")
        self.assertEqual(store.call_args.kwargs["metadata"]["endpoint"], "https://api.example.test/documents")

    def test_local_pages_register_only_after_ocr_succeeds(self):
        stored = {
            "dataset_id": "data_local_pages",
            "dataset_name": "Manual_Pages",
            "source": "C:\\Manual",
            "scope": "local",
            "type": "pages",
            "origin": "local_pages",
            "scenario": "Service documentation",
            "created_at": "2026-01-01T00:00:00+00:00",
            "embedding_model": "all-MiniLM-L6-v2",
            "folder": "C:\\Manual",
            "page_type": "double",
            "ocr_engine": "PaddleOCR / PPStructureV3",
            "items": 2,
        }
        with (
            patch.object(server, "collect_page_files", return_value=["page-01.png"]) as collect,
            patch.object(server, "extract_pages", return_value="## Page 1\n\nExtracted page text.") as extract,
            patch.object(server, "store_text_dataset", return_value=stored) as store,
        ):
            result = self.client.post(
                "/datasets/import/pages",
                json={
                    "source_type": "LOCAL",
                    "source_path": "C:\\Manual",
                    "page_type": "DOUBLE",
                    "scenario": "Service documentation",
                },
            )

        self.assertEqual(result.status_code, 200)
        collect.assert_called_once_with("C:\\Manual")
        extract.assert_called_once_with(["page-01.png"], "double")
        self.assertEqual(store.call_args.kwargs["data_type"], "PAGES")
        self.assertEqual(store.call_args.kwargs["source_type"], "LOCAL")
        self.assertEqual(store.call_args.kwargs["text"], "## Page 1\n\nExtracted page text.")
        self.assertEqual(
            store.call_args.kwargs["metadata"]["ocr_engine"],
            "PaddleOCR PP-OCRv6 medium (CPU)",
        )
        self.assertEqual(store.call_args.kwargs["metadata"]["page_count"], 1)

    def test_failed_ocr_does_not_register_partial_page_dataset(self):
        with (
            patch.object(server, "collect_page_files", return_value=["damaged.pdf"]),
            patch.object(server, "extract_pages", side_effect=RuntimeError("page rendering failed")),
            patch.object(server, "store_text_dataset") as store,
        ):
            result = self.client.post(
                "/datasets/import/pages",
                json={"scope": "local", "source": "damaged.pdf"},
            )

        self.assertEqual(result.status_code, 422)
        self.assertIn("page rendering failed", result.json()["detail"])
        store.assert_not_called()

    def test_pages_import_job_reports_live_ocr_progress(self):
        ocr_started = threading.Event()
        continue_ocr = threading.Event()
        stored = {
            "id": "data_progress_pages",
            "dataset_id": "data_progress_pages",
            "name": "Progress Pages",
            "source_type": "LOCAL",
            "data_type": "PAGES",
            "items": 2,
        }

        def extract(paths, page_type, progress_callback=None):
            self.assertEqual(page_type, "double")
            progress_callback(1, 2)
            ocr_started.set()
            if not continue_ocr.wait(timeout=5):
                raise RuntimeError("Timed out waiting for progress test.")
            return "## Page 1\n\nPage one.\n\n## Page 2\n\nPage two."

        with (
            patch.object(server, "collect_page_files", return_value=["spread.jpg"]),
            patch.object(server, "extract_pages", side_effect=extract),
            patch.object(server, "_store_text_import", return_value=stored),
        ):
            started = self.client.post(
                "/datasets/import/pages/jobs",
                json={
                    "source_type": "LOCAL",
                    "source_path": "C:\\Manual",
                    "page_type": "DOUBLE",
                },
            )
            self.assertEqual(started.status_code, 202)
            job_id = started.json()["job_id"]
            self.assertTrue(ocr_started.wait(timeout=5))
            progress = self.client.get(f"/datasets/import/jobs/{job_id}")
            self.assertEqual(progress.status_code, 200)
            self.assertEqual(progress.json()["phase"], "OCR")
            self.assertEqual(progress.json()["percent"], 44)
            self.assertEqual(progress.json()["detail"], "OCR processed 1 of 2 pages")
            continue_ocr.set()

            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                finished = self.client.get(f"/datasets/import/jobs/{job_id}").json()
                if finished["status"] in {"complete", "failed"}:
                    break
                time.sleep(0.02)

        self.assertEqual(finished["status"], "complete")
        self.assertEqual(finished["percent"], 100)
        self.assertEqual(finished["result"]["id"], "data_progress_pages")

    def test_text_import_job_reports_embedding_progress(self):
        embedding_started = threading.Event()
        continue_embedding = threading.Event()
        stored = {
            "id": "data_progress_text",
            "dataset_id": "data_progress_text",
            "name": "Progress Text",
            "source_type": "LOCAL",
            "data_type": "TEXT",
            "items": 2,
        }

        def store_text(**kwargs):
            callback = kwargs["progress_callback"]
            callback("embedding", 1, 2)
            embedding_started.set()
            if not continue_embedding.wait(timeout=5):
                raise RuntimeError("Timed out waiting for progress test.")
            callback("embedding", 2, 2)
            callback("saving", 1, 1)
            return stored

        with patch.object(server, "_store_text_import", side_effect=store_text):
            started = self.client.post(
                "/datasets/import/text/jobs",
                json={
                    "source_type": "LOCAL",
                    "name": "Progress Text",
                    "text": "A long enough local text passage for progress reporting.",
                },
            )
            self.assertEqual(started.status_code, 202)
            job_id = started.json()["job_id"]
            self.assertTrue(embedding_started.wait(timeout=5))
            progress = self.client.get(f"/datasets/import/jobs/{job_id}").json()
            self.assertEqual(progress["phase"], "Embedding")
            self.assertEqual(progress["percent"], 57)
            self.assertEqual(progress["detail"], "Embedded 1 of 2 passages")
            continue_embedding.set()

            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                finished = self.client.get(f"/datasets/import/jobs/{job_id}").json()
                if finished["status"] in {"complete", "failed"}:
                    break
                time.sleep(0.02)

        self.assertEqual(finished["status"], "complete")
        self.assertEqual(finished["percent"], 100)
        self.assertEqual(finished["result"]["id"], "data_progress_text")

    def test_online_html_pages_record_the_text_extraction_engine(self):
        response = Mock()
        response.headers = {"content-type": "text/html"}
        response.content = b"<html><body>Online page evidence.</body></html>"
        response.text = "<html><body>Online page evidence.</body></html>"
        stored = {
            "dataset_id": "data_api_pages",
            "dataset_name": "Online_Page",
            "source": "https://docs.example.test/page",
            "scope": "api",
            "type": "pages",
            "origin": "api_pages",
            "scenario": "Reference",
            "created_at": "2026-01-01T00:00:00+00:00",
            "embedding_model": "all-MiniLM-L6-v2",
            "api_name": "docs.example.test",
            "endpoint": "https://docs.example.test/page",
            "items": 1,
        }
        with (
            patch.object(server, "_online_response", return_value=response),
            patch.object(server, "store_text_dataset", return_value=stored) as store,
        ):
            result = self.client.post(
                "/datasets/import/pages",
                json={
                    "source_type": "ONLINE_API",
                    "source_url": "https://docs.example.test/page",
                    "page_type": "SINGLE",
                },
            )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(store.call_args.kwargs["metadata"]["ocr_engine"], "HTMLParser")
        self.assertEqual(
            store.call_args.kwargs["metadata"]["processing_status"],
            "READY",
        )

    def test_status_separates_registered_local_and_api_data(self):
        catalog = {
            "data_local": {
                "dataset_id": "data_local",
                "dataset_name": "Local_Manual",
                "source": "C:\\Manual",
                "scope": "local",
                "type": "pages",
                "origin": "local_pages",
                "scenario": "Maintenance",
                "created_at": "2026-01-01T00:00:00+00:00",
                "embedding_model": "all-MiniLM-L6-v2",
                "folder": "C:\\Manual",
                "page_type": "single",
                "ocr_engine": "PaddleOCR",
                "items": 4,
            },
            "data_api": {
                "dataset_id": "data_api",
                "dataset_name": "API_Manual",
                "source": "https://api.example.test/manual",
                "scope": "api",
                "type": "embedded",
                "origin": "api_embedded",
                "scenario": "Maintenance",
                "created_at": "2026-01-01T00:00:00+00:00",
                "embedding_model": "all-MiniLM-L6-v2",
                "api_name": "Maintenance API",
                "endpoint": "https://api.example.test/manual",
                "items": 2,
            },
        }
        with (
            patch.object(dataset_registry, "load_catalog", return_value=catalog),
            patch.object(dataset_registry, "load_registry", return_value=[]),
        ):
            result = self.client.get("/datasets/status")

        self.assertEqual(result.status_code, 200)
        groups = result.json()["groups"]
        self.assertEqual([item["dataset_id"] for item in groups["local"]["pages"]], ["data_local"])
        self.assertEqual([item["dataset_id"] for item in groups["api"]["embedded"]], ["data_api"])
        self.assertEqual(groups["local"]["pages"][0]["data_type"], "PAGES")
        self.assertEqual(groups["api"]["embedded"][0]["data_type"], "EMBEDDED")

    def test_homepage_exposes_separated_data_menus_without_retired_sources(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Local Data", response.text)
        self.assertIn("Online API Data", response.text)
        self.assertIn("dataset-watermark", response.text)
        self.assertNotIn("Hugging Face", response.text)
        self.assertNotIn("Aircraft book", response.text)

    def test_api_key_is_sent_as_bearer_without_being_rewritten(self):
        self.assertEqual(
            server._api_headers("sample-token"),
            {"Authorization": "Bearer sample-token"},
        )

    def test_invalid_json_response_is_not_registered_as_raw_text(self):
        response = Mock()
        response.headers = {"content-type": "application/json"}
        response.text = "{ not valid JSON"
        response.json.side_effect = ValueError("invalid JSON")
        with (
            patch.object(server, "_online_response", return_value=response),
            patch.object(server, "store_text_dataset") as store,
        ):
            result = self.client.post(
                "/datasets/import/text",
                json={"scope": "api", "source": "https://api.example.test/documents"},
            )

        self.assertEqual(result.status_code, 422)
        self.assertIn("malformed JSON", result.json()["detail"])
        store.assert_not_called()
        self.assertEqual(
            server._api_headers("Bearer sample-token"),
            {"Authorization": "Bearer sample-token"},
        )
