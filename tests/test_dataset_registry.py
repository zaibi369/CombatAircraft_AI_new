import unittest
from unittest.mock import patch

from pydantic import ValidationError

import api_dataset_registry
import dataset_registry
from dataset_contract import DatasetRecord, canonical_dataset_record


class DatasetRegistryTests(unittest.TestCase):
    def setUp(self):
        self.remote_text = api_dataset_registry.ApiDatasetConfig.model_validate(
            {
                "id": "remote_manual",
                "name": "Remote Manual",
                "mode": "text",
                "data_url": "https://data.example.test/manual",
                "database": {
                    "type": "chroma",
                    "url": "https://chroma.example.test",
                    "collection": "manual",
                },
            }
        )

    def test_local_and_configured_datasets_share_one_selection_contract(self):
        catalog = {
            "data_local": {
                "dataset_id": "data_local",
                "dataset_name": "Local Manual",
                "source": "C:\\Manual",
                "type": "pages",
                "scope": "local",
                "scenario": "Maintenance",
                "created_at": "2026-01-01T00:00:00+00:00",
                "embedding_model": "all-MiniLM-L6-v2",
                "origin": "local_pages",
                "items": 4,
                "folder": "C:\\Manual",
                "page_type": "double",
                "ocr_engine": "PaddleOCR / PPStructureV3",
            }
        }
        with (
            patch.object(dataset_registry, "load_catalog", return_value=catalog),
            patch.object(dataset_registry, "load_registry", return_value=[self.remote_text]),
        ):
            result = dataset_registry.list_datasets(prepared_datasets={})

        local = result["datasets"]["data_local"]
        remote = result["datasets"]["remote_manual"]
        shared_fields = {
            "id",
            "name",
            "source_type",
            "data_type",
            "status",
            "created_at",
            "updated_at",
            "metadata",
            "storage_location",
            "dataset_id",
            "dataset_name",
            "name",
            "source",
            "type",
            "scope",
            "scenario",
            "embedding_model",
            "origin",
            "items",
            "indexed",
        }
        self.assertTrue(shared_fields.issubset(local))
        self.assertTrue(shared_fields.issubset(remote))
        self.assertEqual(local["type"], "pages")
        self.assertEqual(remote["type"], "text")
        self.assertEqual(remote["scope"], "api")
        self.assertEqual(local["source_type"], "LOCAL")
        self.assertEqual(local["data_type"], "PAGES")
        self.assertEqual(local["page_type"], "DOUBLE")
        self.assertEqual(local["page_count"], 4)
        self.assertEqual(local["processing_status"], "READY")
        self.assertEqual(remote["source_type"], "ONLINE_API")
        self.assertEqual(remote["data_type"], "TEXT")
        self.assertIn("retrieval_metadata", remote)
        self.assertFalse(remote["indexed"])
        self.assertEqual(result["groups"]["local"]["pages"], [local])
        self.assertEqual(result["groups"]["api"]["text"], [remote])

    def test_canonical_schema_requires_page_provenance(self):
        with self.assertRaisesRegex(ValidationError, "page_type, page_count, and ocr_engine"):
            DatasetRecord.model_validate(
                {
                    "id": "data_pages",
                    "name": "Manual pages",
                    "source_type": "LOCAL",
                    "data_type": "PAGES",
                    "scenario": "Maintenance",
                    "status": "READY",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                    "metadata": {},
                    "storage_location": "chroma://manual",
                }
            )

    def test_canonical_embedded_schema_requires_vector_compatibility_metadata(self):
        with self.assertRaisesRegex(ValidationError, "embedding_model, embedding_dimensions"):
            DatasetRecord.model_validate(
                {
                    "id": "data_vectors",
                    "name": "Vectors",
                    "source_type": "LOCAL",
                    "data_type": "EMBEDDED",
                    "scenario": "Testing",
                    "status": "READY",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                    "metadata": {},
                    "storage_location": "chroma://vectors",
                }
            )

    def test_catalog_rejects_unknown_source_type_instead_of_coercing_to_local(self):
        with self.assertRaisesRegex(ValueError, "Expected LOCAL or ONLINE_API"):
            canonical_dataset_record(
                {
                    "id": "data_invalid",
                    "name": "Invalid source",
                    "source_type": "AIRCRAFT",
                    "data_type": "TEXT",
                    "scenario": "Testing",
                    "status": "READY",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                    "metadata": {},
                    "storage_location": "chroma://invalid",
                }
            )

    def test_registry_rejects_ids_shared_by_catalog_and_remote_config(self):
        catalog = {
            "remote_manual": {
                "dataset_id": "remote_manual",
                "dataset_name": "Local collision",
                "source": "local.txt",
                "type": "text",
                "scope": "local",
                "scenario": "Testing",
                "embedding_model": "all-MiniLM-L6-v2",
                "origin": "local_text",
                "items": 1,
            }
        }
        with (
            patch.object(dataset_registry, "load_catalog", return_value=catalog),
            patch.object(dataset_registry, "load_registry", return_value=[self.remote_text]),
            self.assertRaisesRegex(ValueError, "used by both"),
        ):
            dataset_registry.list_datasets(prepared_datasets={})


if __name__ == "__main__":
    unittest.main()
