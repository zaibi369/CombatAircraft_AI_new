import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import api_dataset_registry
import server
from fastapi.testclient import TestClient


class FakeEmbeddingFunction:
    def __call__(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeFastEmbedModel:
    def __init__(self, vectors=None):
        self.vectors = vectors
        self.embed_calls = []

    def embed(self, texts):
        self.embed_calls.append(texts)
        return self.vectors or [[0.4, 0.5, 0.6, 0.7] for _ in texts]


class ApiDatasetRegistryTests(unittest.TestCase):
    def make_dataset(self, database_type, mode="preembedded", **database_options):
        database = {
            "type": database_type,
            "url": "https://vector.example.test",
            "collection": "History",
            **database_options,
        }
        return api_dataset_registry.ApiDatasetConfig.model_validate(
            {
                "id": "history_api",
                "name": "History API",
                "mode": mode,
                "embedding_dimensions": 384 if mode == "preembedded" else None,
                "data_url": "https://data.example.test/history" if mode == "text" else None,
                "database": database,
            }
        )

    def test_registry_loads_configured_datasets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api_datasets.json"
            path.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "id": "history_api",
                                "name": "History API",
                                "mode": "preembedded",
                                "embedding_provider": "ollama",
                                "embedding_model": "nomic-embed-text",
                                "embedding_dimensions": 768,
                                "database": {
                                    "type": "pinecone",
                                    "url": "https://index.example.test",
                                    "collection": "history",
                                    "api_key_env": "PINECONE_KEY",
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            datasets = api_dataset_registry.load_registry(path)

        self.assertEqual(len(datasets), 1)
        self.assertEqual(datasets[0].database.type, "pinecone")
        self.assertEqual(datasets[0].mode, "preembedded")
        self.assertEqual(datasets[0].embedding_provider, "ollama")
        self.assertEqual(datasets[0].embedding_model, "nomic-embed-text")

    def test_preembedded_registry_requires_declared_vector_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api_datasets.json"
            path.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "id": "history_api",
                                "name": "History API",
                                "mode": "preembedded",
                                "database": {
                                    "type": "chroma",
                                    "url": "https://chroma.example.test",
                                    "collection": "history",
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "embedding_dimensions"):
                api_dataset_registry.load_registry(path)

    def test_registry_allows_embedding_provider_and_model_per_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api_datasets.json"
            path.write_text(
                json.dumps(
                    {
                        "default_embedding_model": "all-MiniLM-L6-v2",
                        "default_embedding_provider": "local",
                        "datasets": [
                            {
                                "id": "history_api",
                                "name": "History API",
                                "mode": "preembedded",
                                "embedding_provider": "ollama",
                                "embedding_model": "nomic-embed-text",
                                "embedding_dimensions": 768,
                                "database": {
                                    "type": "pinecone",
                                    "url": "https://index.example.test",
                                    "collection": "history",
                                    "api_key_env": "PINECONE_KEY",
                                },
                            },
                            {
                                "id": "default_model_api",
                                "name": "Default model API",
                                "mode": "preembedded",
                                "embedding_dimensions": 384,
                                "database": {
                                    "type": "chroma",
                                    "url": "https://chroma.example.test",
                                    "collection": "history",
                                },
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            datasets = api_dataset_registry.load_registry(path)

        self.assertEqual(datasets[0].embedding_model, "nomic-embed-text")
        self.assertEqual(datasets[0].embedding_provider, "ollama")
        self.assertEqual(
            datasets[1].embedding_model,
            "all-MiniLM-L6-v2",
        )

    def test_registry_rejects_two_datasets_sharing_same_vector_destination(self):
        entry = {
            "name": "Vector dataset",
            "mode": "preembedded",
            "embedding_dimensions": 384,
            "database": {
                "type": "chroma",
                "url": "https://chroma.example.test",
                "collection": "shared",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api_datasets.json"
            path.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {"id": "history_one", **entry},
                            {"id": "history_two", **entry},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "same vector database destination"):
                api_dataset_registry.load_registry(path)

    def test_registry_accepts_different_collections_for_separate_datasets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api_datasets.json"
            path.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "id": "history_one",
                                "name": "History one",
                                "mode": "preembedded",
                                "embedding_dimensions": 384,
                                "database": {
                                    "type": "chroma",
                                    "url": "https://chroma.example.test",
                                    "collection": "history_one",
                                },
                            },
                            {
                                "id": "history_two",
                                "name": "History two",
                                "mode": "preembedded",
                                "embedding_dimensions": 384,
                                "database": {
                                    "type": "chroma",
                                    "url": "https://chroma.example.test",
                                    "collection": "history_two",
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            datasets = api_dataset_registry.load_registry(path)

        self.assertEqual([dataset.id for dataset in datasets], ["history_one", "history_two"])

    def test_question_vectors_use_configured_ollama_provider(self):
        dataset = self.make_dataset("pinecone", api_key_env="PINECONE_KEY")
        dataset.embedding_provider = "ollama"
        dataset.embedding_model = "nomic-embed-text"
        vector_response = unittest.mock.Mock()
        vector_response.status_code = 200
        vector_response.json.return_value = [[0.4, 0.5, 0.6, 0.7]]
        query_response = unittest.mock.Mock()
        query_response.json.return_value = {
            "matches": [{"metadata": {"text": "Matching evidence."}}]
        }
        with (
            patch.dict("os.environ", {"PINECONE_KEY": "test-key"}),
            patch.object(
                api_dataset_registry.requests,
                "post",
                side_effect=[vector_response, query_response],
            ) as post,
        ):
            results = api_dataset_registry.query_api_dataset(dataset, "Question")

        self.assertEqual(results[0]["text"], "Matching evidence.")
        self.assertEqual(
            post.call_args_list[0].args[0],
            "http://127.0.0.1:11434/api/embed",
        )
        self.assertEqual(
            post.call_args_list[0].kwargs["json"],
            {"model": "nomic-embed-text", "input": ["Question"]},
        )

    def test_question_vectors_use_ollama_embed_api(self):
        dataset = self.make_dataset("chroma")
        dataset.embedding_provider = "ollama"
        dataset.embedding_model = "embeddinggemma"
        embedding_response = unittest.mock.Mock()
        embedding_response.json.return_value = {"embeddings": [[0.4, 0.5, 0.6]]}
        collection = unittest.mock.Mock()
        collection.query.return_value = {
            "documents": [["Ollama evidence."]],
            "metadatas": [[{"title": "History"}]],
        }
        client = unittest.mock.Mock()
        client.get_collection.return_value = collection
        with (
            patch.object(
                api_dataset_registry.requests,
                "post",
                return_value=embedding_response,
            ) as post,
            patch.object(api_dataset_registry.chromadb, "HttpClient", return_value=client),
        ):
            results = api_dataset_registry.query_api_dataset(dataset, "Question")

        self.assertEqual(results[0]["text"], "Ollama evidence.")
        self.assertEqual(
            post.call_args.kwargs["json"],
            {"model": "embeddinggemma", "input": ["Question"]},
        )
        self.assertEqual(collection.query.call_args.kwargs["query_embeddings"], [[0.4, 0.5, 0.6]])

    def test_token_vectors_are_pooled_using_registry_strategy(self):
        token_vectors = [
            [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
            [[2.0, 4.0], [4.0, 8.0], [6.0, 12.0]],
        ]
        self.assertEqual(
            api_dataset_registry._embedding_batch(token_vectors, 2, "mean"),
            [[3.0, 4.0], [4.0, 8.0]],
        )
        self.assertEqual(
            api_dataset_registry._embedding_batch(token_vectors, 2, "cls"),
            [[1.0, 2.0], [2.0, 4.0]],
        )
        self.assertEqual(
            api_dataset_registry._embedding_batch(token_vectors, 2, "last_token"),
            [[5.0, 6.0], [6.0, 12.0]],
        )

    def test_text_indexing_uses_custom_local_embedding_model(self):
        model = FakeFastEmbedModel()
        dataset = self.make_dataset(
            "pinecone",
            mode="text",
            api_key_env="PINECONE_KEY",
        )
        dataset.embedding_provider = "local"
        dataset.embedding_model = "BAAI/bge-small-en-v1.5"
        response = unittest.mock.Mock()
        with (
            patch.dict("os.environ", {"PINECONE_KEY": "test-key"}),
            patch.object(api_dataset_registry, "fetch_text_documents", return_value=[
                ("id-1", "History", "A history passage.")
            ]),
            patch.object(api_dataset_registry, "_load_embedding_model", return_value=model),
            patch.object(api_dataset_registry.requests, "post", return_value=response),
        ):
            api_dataset_registry.index_text_dataset(dataset)

        self.assertEqual(model.embed_calls, [["A history passage."]])

    def test_default_model_uses_existing_local_embedding_function(self):
        with patch.object(
            api_dataset_registry,
            "local_embedding_function",
            return_value=FakeEmbeddingFunction(),
        ) as default_embedding:
            vectors = api_dataset_registry._vectors(["Question"])

        self.assertEqual(vectors, [[0.1, 0.2, 0.3]])
        default_embedding.assert_called_once()


    def test_text_dataset_records_are_extracted_from_api_rows(self):
        response = unittest.mock.Mock()
        response.json.return_value = {
            "rows": [
                {
                    "row": {
                        "title": "History",
                        "question": "What happened in 1946?",
                        "answer": "Churchill delivered the Iron Curtain speech.",
                    }
                }
            ]
        }
        with patch.object(api_dataset_registry.requests, "get", return_value=response):
            documents = api_dataset_registry.fetch_text_documents(
                self.make_dataset("chroma", mode="text")
            )

        self.assertEqual(len(documents), 1)
        self.assertIn("What happened in 1946?", documents[0][2])
        self.assertIn("Iron Curtain speech", documents[0][2])

    def test_text_api_qa_chunks_retain_the_question_for_retrieval(self):
        answer = " ".join(f"detail{index}" for index in range(250))
        response = unittest.mock.Mock()
        response.json.return_value = {
            "records": [
                {
                    "question": "Why did this history event matter?",
                    "answer": answer,
                }
            ]
        }
        with patch.object(api_dataset_registry.requests, "get", return_value=response):
            documents = api_dataset_registry.fetch_text_documents(
                self.make_dataset("chroma", mode="text")
            )

        self.assertEqual(len(documents), 1)
        self.assertTrue(
            all("Question: Why did this history event matter?" in text for _, _, text in documents)
        )

    def test_chroma_query_uses_remote_collection_query_protocol(self):
        collection = unittest.mock.Mock()
        collection.query.return_value = {
            "documents": [["The Iron Curtain speech was delivered in 1946."]],
            "metadatas": [[{"title": "History"}]],
        }
        client = unittest.mock.Mock()
        client.get_collection.return_value = collection
        with (
            patch.object(api_dataset_registry, "local_embedding_function", return_value=FakeEmbeddingFunction()),
            patch.object(api_dataset_registry.chromadb, "HttpClient", return_value=client),
        ):
            result = api_dataset_registry.query_api_dataset(
                self.make_dataset("chroma"),
                "When was the Iron Curtain speech?",
            )

        self.assertIn("1946", result[0]["text"])
        collection.query.assert_called_once()
        self.assertEqual(
            collection.query.call_args.kwargs["query_embeddings"],
            [[0.1, 0.2, 0.3]],
        )

    def test_pinecone_query_sends_vector_and_namespace(self):
        response = unittest.mock.Mock()
        response.json.return_value = {
            "matches": [
                {
                    "metadata": {
                        "text": "Churchill delivered the Iron Curtain speech.",
                        "title": "History",
                    }
                }
            ]
        }
        dataset = self.make_dataset(
            "pinecone",
            api_key_env="PINECONE_KEY",
            namespace="history",
        )
        with (
            patch.dict("os.environ", {"PINECONE_KEY": "test-key"}),
            patch.object(api_dataset_registry, "local_embedding_function", return_value=FakeEmbeddingFunction()),
            patch.object(api_dataset_registry.requests, "post", return_value=response) as post,
        ):
            result = api_dataset_registry.query_api_dataset(dataset, "Churchill speech")

        self.assertIn("Churchill", result[0]["text"])
        self.assertEqual(post.call_args.kwargs["json"]["namespace"], "history")
        self.assertEqual(post.call_args.kwargs["headers"]["Api-Key"], "test-key")

    def test_weaviate_query_uses_graphql_near_vector_protocol(self):
        response = unittest.mock.Mock()
        response.json.return_value = {
            "data": {
                "Get": {
                    "History": [
                        {
                            "text": "Churchill delivered the Iron Curtain speech.",
                            "title": "History",
                        }
                    ]
                }
            }
        }
        dataset = self.make_dataset(
            "weaviate",
            api_key_env="WEAVIATE_KEY",
            text_property="text",
            title_property="title",
        )
        with (
            patch.dict("os.environ", {"WEAVIATE_KEY": "test-key"}),
            patch.object(api_dataset_registry, "local_embedding_function", return_value=FakeEmbeddingFunction()),
            patch.object(api_dataset_registry.requests, "post", return_value=response) as post,
        ):
            result = api_dataset_registry.query_api_dataset(dataset, "Churchill speech")

        self.assertIn("Churchill", result[0]["text"])
        self.assertIn("nearVector", post.call_args.kwargs["json"]["query"])
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")

    def test_text_mode_upserts_embedded_vectors_to_pinecone(self):
        dataset = self.make_dataset(
            "pinecone",
            mode="text",
            api_key_env="PINECONE_KEY",
            namespace="history",
        )
        response = unittest.mock.Mock()
        with (
            patch.dict("os.environ", {"PINECONE_KEY": "test-key"}),
            patch.object(api_dataset_registry, "fetch_text_documents", return_value=[
                ("id-1", "History", "A short history passage.")
            ]),
            patch.object(api_dataset_registry, "local_embedding_function", return_value=FakeEmbeddingFunction()),
            patch.object(api_dataset_registry.requests, "post", return_value=response) as post,
        ):
            count = api_dataset_registry.index_text_dataset(dataset)

        self.assertEqual(count, 1)
        vector = post.call_args.kwargs["json"]["vectors"][0]
        self.assertEqual(vector["values"], [0.1, 0.2, 0.3])
        self.assertEqual(vector["metadata"]["text"], "A short history passage.")

    def test_text_mode_upserts_embeddings_to_remote_chroma(self):
        dataset = self.make_dataset("chroma", mode="text")
        collection = unittest.mock.Mock()
        client = unittest.mock.Mock()
        client.get_or_create_collection.return_value = collection
        with (
            patch.object(api_dataset_registry, "fetch_text_documents", return_value=[
                ("id-1", "History", "A short history passage.")
            ]),
            patch.object(api_dataset_registry, "local_embedding_function", return_value=FakeEmbeddingFunction()),
            patch.object(api_dataset_registry.chromadb, "HttpClient", return_value=client),
        ):
            count = api_dataset_registry.index_text_dataset(dataset)

        self.assertEqual(count, 1)
        collection.upsert.assert_called_once()
        self.assertEqual(
            collection.upsert.call_args.kwargs["embeddings"],
            [[0.1, 0.2, 0.3]],
        )

    def test_text_mode_upserts_embeddings_to_weaviate(self):
        dataset = self.make_dataset(
            "weaviate",
            mode="text",
            text_property="text",
            title_property="title",
        )
        response = unittest.mock.Mock()
        response.status_code = 200
        with (
            patch.object(api_dataset_registry, "fetch_text_documents", return_value=[
                ("id-1", "History", "A short history passage.")
            ]),
            patch.object(api_dataset_registry, "local_embedding_function", return_value=FakeEmbeddingFunction()),
            patch.object(api_dataset_registry.requests, "put", return_value=response) as put,
        ):
            count = api_dataset_registry.index_text_dataset(dataset)

        self.assertEqual(count, 1)
        self.assertEqual(put.call_args.kwargs["json"]["properties"]["text"], "A short history passage.")
        self.assertEqual(put.call_args.kwargs["json"]["class"], "History")

    def test_registered_text_api_is_indexed_when_selected(self):
        entry = {
            "id": "registry_text_index_test",
            "name": "Registry text index test",
            "mode": "text",
            "data_url": "https://data.example.test/history",
            "database": {
                "type": "chroma",
                "url": "https://chroma.example.test",
                "collection": "history",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "api_datasets.json"
            registry_path.write_text(json.dumps({"datasets": [entry]}), encoding="utf-8")
            with (
                patch.object(server, "API_DATASETS_PATH", registry_path),
                patch.object(server, "index_text_dataset", return_value=12) as index_dataset,
            ):
                response = TestClient(server.app).post(
                    "/datasets/index",
                    json={"collection": entry["id"]},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], 12)
        self.assertEqual(index_dataset.call_args.args[0].id, entry["id"])

    def test_registered_source_can_be_selected_through_ask_api(self):
        with (
            patch.object(server, "local_context", return_value="[History]\nEvidence.") as local_context,
            patch.object(server, "generate_reply", return_value="Answer [History]."),
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "Question",
                    "search_mode": "local",
                    "collection": "registered_history",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "Answer [History].")
        local_context.assert_called_once_with("Question", "registered_history")


if __name__ == "__main__":
    unittest.main()
