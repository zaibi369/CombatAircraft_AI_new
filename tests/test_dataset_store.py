import tempfile
import json
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import chromadb
from chromadb.api.types import EmbeddingFunction

import dataset_store


class RejectingEmbeddingFunction(EmbeddingFunction):
    def __init__(self):
        pass

    def __call__(self, input):
        raise AssertionError("Supplied embedded vectors must not be re-embedded.")

    @staticmethod
    def name():
        return "rejecting-test-embedding"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return RejectingEmbeddingFunction()

    @staticmethod
    def validate_config(config):
        return None


class DatasetStoreTests(unittest.TestCase):
    def tearDown(self):
        chromadb.api.client.SharedSystemClient.clear_system_cache()

    def test_stores_supplied_vectors_directly_and_records_source_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            client = chromadb.EphemeralClient()
            with (
                patch.object(
                    dataset_store,
                    "local_embedding_function",
                    return_value=RejectingEmbeddingFunction(),
                ),
                patch.object(dataset_store.chromadb, "PersistentClient", return_value=client),
            ):
                stored = dataset_store.store_embedded_dataset(
                    name="",
                    source="https://api.example.test/vectors",
                    source_type="ONLINE_API",
                    data_type="EMBEDDED",
                    scenario="Maintenance reference",
                    passages=[{"text": "Maintenance inspection procedure."}],
                    vectors=[[0.0] * 384],
                    embedding_model=dataset_store.EMBEDDING_MODEL,
                    metadata={
                        "api_name": "Maintenance API",
                        "endpoint": "https://api.example.test/vectors",
                    },
                    vector_db_path=Path(directory),
                )

            catalog = dataset_store.load_catalog(Path(directory))

        self.assertEqual(stored["scope"], "api")
        self.assertEqual(stored["type"], "embedded")
        self.assertEqual(stored["scenario"], "Maintenance reference")
        self.assertEqual(stored["api_name"], "Maintenance API")
        self.assertEqual(stored["endpoint"], "https://api.example.test/vectors")
        self.assertNotIn("dataset_type", stored)
        self.assertEqual(stored["source_type"], "ONLINE_API")
        self.assertEqual(stored["data_type"], "EMBEDDED")
        self.assertEqual(stored["embedding_dimensions"], 384)
        self.assertEqual(stored["vector_format"], "float32[]")
        self.assertTrue(stored["storage_location"])
        self.assertTrue(stored["updated_at"])
        self.assertEqual(len(catalog), 1)
        self.assertTrue(stored["dataset_name"])
        stored_record = next(iter(catalog.values()))
        self.assertEqual(stored_record["id"], stored["id"])
        self.assertNotIn("dataset_id", stored_record)
        self.assertIn("collection", stored_record["metadata"])

    def test_persistent_client_initialization_is_serialized_across_threads(self):
        active = 0
        maximum_active = 0
        state_lock = threading.Lock()

        def create_client(*, path):
            nonlocal active, maximum_active
            with state_lock:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.01)
            with state_lock:
                active -= 1
            return path

        with (
            patch.object(dataset_store.chromadb, "PersistentClient", side_effect=create_client),
            ThreadPoolExecutor(max_workers=8) as executor,
        ):
            clients = list(executor.map(
                lambda _: dataset_store.persistent_vector_client(Path("shared-db")),
                range(8),
            ))

        self.assertEqual(clients, ["shared-db"] * 8)
        self.assertEqual(maximum_active, 1)

    def test_rejects_incompatible_dimensions_and_non_finite_vectors(self):
        with tempfile.TemporaryDirectory() as directory:
            arguments = {
                "name": "Vector data",
                "source": "local-file.json",
                "source_type": "LOCAL",
                "data_type": "EMBEDDED",
                "scenario": "Testing",
                "passages": [{"text": "Sample source text"}],
                "embedding_model": dataset_store.EMBEDDING_MODEL,
                "vector_db_path": Path(directory),
            }
            with self.assertRaisesRegex(ValueError, "384-dimensional"):
                dataset_store.store_embedded_dataset(
                    **arguments,
                    vectors=[[0.1, 0.2, 0.3]],
                )
            with self.assertRaisesRegex(ValueError, "invalid numeric values"):
                dataset_store.store_embedded_dataset(
                    **arguments,
                    vectors=[[float("nan")] * 384],
                )

    def test_rejects_duplicate_source_and_content(self):
        with tempfile.TemporaryDirectory() as directory:
            client = chromadb.EphemeralClient()
            with (
                patch.object(
                    dataset_store,
                    "local_embedding_function",
                    return_value=RejectingEmbeddingFunction(),
                ),
                patch.object(dataset_store.chromadb, "PersistentClient", return_value=client),
            ):
                arguments = {
                    "name": "Reference",
                    "source": "local.txt",
                    "source_type": "LOCAL",
                    "data_type": "EMBEDDED",
                    "scenario": "Testing",
                    "passages": [{"text": "The same passage."}],
                    "vectors": [[0.0] * 384],
                    "embedding_model": dataset_store.EMBEDDING_MODEL,
                    "metadata": {},
                    "vector_db_path": Path(directory),
                }
                dataset_store.store_embedded_dataset(**arguments)
                with self.assertRaises(FileExistsError):
                    dataset_store.store_embedded_dataset(**arguments)

    def test_generates_meaningful_names_from_content(self):
        self.assertEqual(
            dataset_store.automatic_name("", "Technical manual chapter 02 maintenance checklist"),
            "Technical_manual_chapter_02_maintenance_checklist",
        )

    def test_legacy_catalog_records_are_migrated_to_the_canonical_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "dataset_catalog.json"
            catalog_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "datasets": {
                            "data_legacy": {
                                "dataset_id": "data_legacy",
                                "dataset_name": "Legacy Manual",
                                "source": "C:\\Manual",
                                "type": "pages",
                                "scope": "local",
                                "scenario": "Maintenance",
                                "created_at": "2026-01-01T00:00:00+00:00",
                                "embedding_model": dataset_store.EMBEDDING_MODEL,
                                "origin": "local_pages",
                                "items": 3,
                                "folder": "C:\\Manual",
                                "page_type": "double",
                                "ocr_engine": "PaddleOCR",
                                "collection": "legacy_collection",
                                "fingerprint": "legacy-fingerprint",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            migrated = dataset_store.load_catalog(Path(directory))["data_legacy"]
            persisted = json.loads(catalog_path.read_text(encoding="utf-8"))["datasets"]["data_legacy"]

        self.assertEqual(migrated["source_type"], "LOCAL")
        self.assertEqual(migrated["data_type"], "PAGES")
        self.assertEqual(migrated["storage_location"], "chroma:legacy_collection")
        self.assertEqual(migrated["page_type"], "DOUBLE")
        self.assertEqual(migrated["page_count"], 3)
        self.assertEqual(migrated["metadata"]["fingerprint"], "legacy-fingerprint")
        self.assertEqual(persisted, migrated)
        self.assertNotIn("dataset_id", persisted)
