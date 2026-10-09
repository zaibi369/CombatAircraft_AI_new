import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chromadb
from fastapi.testclient import TestClient

import server
from dataset_store import (
    load_catalog,
    save_catalog,
)


class DatasetLifecycleTests(unittest.TestCase):
    def setUp(self):
        chromadb.api.client.SharedSystemClient.clear_system_cache()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name)
        self.dataset_id = "data_delete_test"
        self.collection_name = "source_delete_test"
        self.record = {
            "id": self.dataset_id,
            "name": "Dataset to remove",
            "source_type": "LOCAL",
            "data_type": "TEXT",
            "scenario": "Test",
            "status": "READY",
            "created_at": "2026-10-02T00:00:00+00:00",
            "updated_at": "2026-10-02T00:00:00+00:00",
            "metadata": {
                "source": "local test",
                "collection": self.collection_name,
                "dataset_id": self.dataset_id,
                "items": 1,
            },
            "storage_location": f"chroma://{self.database_path}#{self.collection_name}",
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_dimensions": 384,
        }
        save_catalog({self.dataset_id: self.record}, self.database_path)
        self.client = chromadb.EphemeralClient()
        self.client.create_collection(
            name=self.collection_name,
            metadata={"dataset_id": self.dataset_id},
        )
        self.other_collection = self.client.create_collection(
            name="source_keep_test",
            metadata={"dataset_id": "data_keep_test"},
        )

    def tearDown(self):
        chromadb.api.client.SharedSystemClient.clear_system_cache()
        self.temporary_directory.cleanup()

    def test_trash_restore_and_permanent_delete_routes(self):
        with (
            patch.object(server, "VECTOR_DB_PATH", self.database_path),
            patch("dataset_store.persistent_vector_client", return_value=self.client),
        ):
            client = TestClient(server.app)

            trashed = client.post(f"/datasets/{self.dataset_id}/trash")
            self.assertEqual(trashed.status_code, 200)
            self.assertEqual(load_catalog(self.database_path), {})
            trash_response = client.get("/datasets/trash")
            self.assertEqual(trash_response.status_code, 200)
            self.assertEqual(
                trash_response.json()["datasets"][0]["name"],
                "Dataset to remove",
            )
            self.assertEqual(self.client.get_collection(self.collection_name).count(), 0)

            restored = client.post(f"/datasets/trash/{self.dataset_id}/restore")
            self.assertEqual(restored.status_code, 200)
            self.assertIn(self.dataset_id, load_catalog(self.database_path))
            self.assertEqual(client.get("/datasets/trash").json()["datasets"], [])

            self.assertEqual(
                client.post(f"/datasets/{self.dataset_id}/trash").status_code,
                200,
            )
            deleted = client.delete(f"/datasets/trash/{self.dataset_id}")
            self.assertEqual(deleted.status_code, 200)
            self.assertEqual(client.get("/datasets/trash").json()["datasets"], [])
            self.assertNotIn(
                self.collection_name,
                [collection.name for collection in self.client.list_collections()],
            )
            self.assertIn(
                "source_keep_test",
                [collection.name for collection in self.client.list_collections()],
                "Permanent deletion must leave other datasets' collections untouched.",
            )

    def test_unmanaged_dataset_cannot_be_moved_to_trash(self):
        with patch.object(server, "VECTOR_DB_PATH", self.database_path):
            response = TestClient(server.app).post("/datasets/remote_config/trash")

        self.assertEqual(response.status_code, 404)
        self.assertIn(self.dataset_id, load_catalog(self.database_path))


if __name__ == "__main__":
    unittest.main()
