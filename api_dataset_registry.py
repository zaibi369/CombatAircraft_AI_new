import hashlib
import json
import math
import os
import re
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import chromadb
import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from dataset_store import local_embedding_function
BASE_DIR = Path(__file__).resolve().parent
API_DATASETS_PATH = BASE_DIR / "api_datasets.json"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_PROVIDER = "local"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/embed"
TEXT_FIELDS = ("text", "content", "passage", "context", "answer", "description")
TITLE_FIELDS = ("title", "name", "subject")


class VectorDatabaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["chroma", "pinecone", "weaviate"]
    url: str
    collection: str = Field(min_length=1, max_length=256)
    api_key_env: str | None = None
    namespace: str | None = None
    tenant: str | None = None
    database: str | None = None
    text_property: str = "text"
    title_property: str = "title"
    api_key_header: str | None = None
    api_key_prefix: str | None = None

    @model_validator(mode="after")
    def validate_endpoint(self):
        parsed = urlsplit(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Vector database URL must be an absolute HTTP(S) URL.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Credentials and query strings must not be embedded in database URLs.")
        if self.type == "chroma" and parsed.path not in {"", "/"}:
            raise ValueError("Chroma URL must be the server origin without a path.")
        if self.type == "pinecone" and not self.api_key_env:
            raise ValueError("Pinecone entries must set api_key_env.")
        if self.type == "weaviate":
            for property_name in (self.collection, self.text_property, self.title_property):
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", property_name):
                    raise ValueError("Weaviate class and property names must be valid identifiers.")
        return self


class ApiDatasetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,62}$")
    name: str = Field(min_length=1, max_length=100)
    mode: Literal["text", "preembedded"]
    data_url: str | None = None
    database: VectorDatabaseConfig
    embedding_provider: Literal["local", "ollama"] = DEFAULT_EMBEDDING_PROVIDER
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    embedding_dimensions: int | None = Field(default=None, gt=0)
    normalize_embeddings: bool = False
    pooling: Literal["mean", "cls", "last_token"] = "mean"
    query_prefix: str = ""
    document_prefix: str = ""
    embedding_api_url: str | None = None
    embedding_api_key_env: str | None = None
    api_key_env: str | None = None
    api_key_header: str = "Authorization"
    api_key_prefix: str = "Bearer "

    @model_validator(mode="after")
    def validate_dataset(self):
        if self.mode == "text":
            if not self.data_url:
                raise ValueError("Text API datasets must set data_url.")
            parsed = urlsplit(self.data_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("Dataset data_url must be an absolute HTTP(S) URL.")
            if parsed.username or parsed.password:
                raise ValueError("Credentials must be supplied using an environment variable.")
        if not self.embedding_model.strip():
            raise ValueError("embedding_model must be a non-empty model name or ID.")
        if self.mode == "preembedded" and self.embedding_dimensions is None:
            raise ValueError(
                "Pre-embedded API datasets must declare embedding_dimensions."
            )
        if self.embedding_api_url:
            parsed = urlsplit(self.embedding_api_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("embedding_api_url must be an absolute HTTP(S) URL.")
            if parsed.username or parsed.password:
                raise ValueError("Credentials must be supplied using an environment variable.")
        return self


def load_registry(path: Path = API_DATASETS_PATH) -> list[ApiDatasetConfig]:
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in API dataset registry {path}: {error}") from error

    if not isinstance(registry, dict) or not isinstance(registry.get("datasets"), list):
        raise ValueError("API dataset registry must contain a 'datasets' list.")
    default_model = registry.get("default_embedding_model", DEFAULT_EMBEDDING_MODEL)
    if not isinstance(default_model, str) or not default_model.strip():
        raise ValueError("'default_embedding_model' must be a non-empty model ID string.")
    default_provider = registry.get("default_embedding_provider", DEFAULT_EMBEDDING_PROVIDER)
    if not isinstance(default_provider, str) or default_provider not in {"local", "ollama"}:
        raise ValueError("'default_embedding_provider' must be local or ollama.")
    if any(not isinstance(item, dict) for item in registry["datasets"]):
        raise ValueError("Every API dataset registry entry must be a JSON object.")
    try:
        datasets = [
            ApiDatasetConfig.model_validate(
                {
                    **item,
                    "embedding_provider": item.get("embedding_provider", default_provider),
                    "embedding_model": item.get("embedding_model", default_model),
                }
            )
            for item in registry["datasets"]
        ]
    except ValidationError as error:
        raise ValueError(f"Invalid API dataset registry entry: {error}") from error
    ids = [dataset.id for dataset in datasets]
    if len(ids) != len(set(ids)):
        raise ValueError("API dataset registry IDs must be unique.")
    destinations = {}
    for dataset in datasets:
        destination = _vector_destination(dataset.database)
        previous_id = destinations.get(destination)
        if previous_id is not None:
            raise ValueError(
                f"API datasets '{previous_id}' and '{dataset.id}' use the same vector "
                "database destination. Give each dataset its own collection or namespace."
            )
        destinations[destination] = dataset.id
    return datasets


def _vector_destination(database: VectorDatabaseConfig) -> tuple[str, ...]:
    normalized_url = database.url.rstrip("/").lower()
    if database.type == "chroma":
        return (
            database.type,
            normalized_url,
            database.tenant or "default_tenant",
            database.database or "default_database",
            database.collection,
        )
    if database.type == "pinecone":
        return (
            database.type,
            normalized_url,
            database.collection,
            database.namespace or "",
        )
    return (database.type, normalized_url, database.collection)


def get_registry_dataset(dataset_id: str, path: Path = API_DATASETS_PATH) -> ApiDatasetConfig:
    for dataset in load_registry(path):
        if dataset.id == dataset_id:
            return dataset
    raise ValueError(f"API dataset '{dataset_id}' is not registered.")


def dataset_signature(dataset: ApiDatasetConfig) -> str:
    return dataset.model_dump_json(
        exclude={"api_key_env": True, "database": {"api_key_env": True}}
    )


def _headers(database: VectorDatabaseConfig, extra_key_env: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key_name = database.api_key_env or extra_key_env
    if key_name:
        key = os.getenv(key_name)
        if not key:
            raise ValueError(f"Required API key environment variable '{key_name}' is not set.")
        header = database.api_key_header
        if not header:
            header = {"pinecone": "Api-Key", "weaviate": "Authorization"}.get(
                database.type,
                "Authorization",
            )
        prefix = database.api_key_prefix
        if prefix is None:
            prefix = "" if header.lower() == "api-key" else "Bearer "
        headers[header] = key if key.lower().startswith(prefix.lower()) else f"{prefix}{key}"
    return headers


def _flatten_records(value) -> list[tuple[str, str, str | None]]:
    records = []
    if isinstance(value, list):
        for item in value:
            records.extend(_flatten_records(item))
        return records
    if not isinstance(value, dict):
        return records

    if isinstance(value.get("row"), dict):
        return _flatten_records(value["row"])

    title = next(
        (str(value[field]).strip() for field in TITLE_FIELDS if value.get(field) is not None),
        "API dataset",
    )
    question = value.get("question")
    answer = value.get("answer")
    if isinstance(question, str) and isinstance(answer, str):
        records.append((title, answer.strip(), question.strip()))
        return records

    qa_pairs = value.get("qa_pairs")
    if isinstance(qa_pairs, list):
        for pair in qa_pairs:
            if isinstance(pair, dict):
                records.extend(_flatten_records({**pair, "title": title}))
        if records:
            return records

    for field in TEXT_FIELDS:
        text = value.get(field)
        if isinstance(text, str) and text.strip():
            records.append((title, text.strip(), None))
            return records

    for field in ("rows", "documents", "records", "data", "items", "results"):
        nested = value.get(field)
        if isinstance(nested, (list, dict)):
            records.extend(_flatten_records(nested))
            if records:
                return records
    return records


def fetch_text_documents(dataset: ApiDatasetConfig) -> list[tuple[str, str, str]]:
    headers = {}
    if dataset.api_key_env:
        key = os.getenv(dataset.api_key_env)
        if not key:
            raise ValueError(f"Required API key environment variable '{dataset.api_key_env}' is not set.")
        headers[dataset.api_key_header] = (
            key
            if key.lower().startswith(dataset.api_key_prefix.lower())
            else f"{dataset.api_key_prefix}{key}"
        )
    response = requests.get(dataset.data_url, headers=headers, timeout=60)
    response.raise_for_status()
    records = _flatten_records(response.json())
    documents = []
    for record_index, (title, text, question) in enumerate(records):
        if question:
            chunks = [f"Question: {question}\nAnswer: {text}"]
        else:
            words = text.split()
            chunks = [
                " ".join(words[start:start + 120])
                for start in range(0, len(words), 96)
            ]
        for chunk_index, chunk in enumerate(chunks):
            document_id = hashlib.sha256(
                f"{dataset.id}:{record_index}:{chunk_index}:{chunk}".encode("utf-8")
            ).hexdigest()
            documents.append((document_id, title[:500] or dataset.name, chunk))
    if not documents:
        raise ValueError(
            "Text API returned no indexable records. Expected rows, documents, records, "
            "data, items, or results containing text/content/passage/context or question-answer fields."
        )
    return documents


@lru_cache(maxsize=4)
def _load_embedding_model(model_name: str):
    try:
        from fastembed import TextEmbedding
    except ImportError as error:
        raise RuntimeError(
            "Custom local models require the lightweight fastembed package. "
            "Install it with 'pip install -r requirements-embedding-models.txt'."
        ) from error
    try:
        return TextEmbedding(model_name=model_name)
    except (OSError, ValueError, KeyError) as error:
        raise ValueError(
            f"Could not load local embedding model '{model_name}'. Check that the "
            "model is supported by FastEmbed and available for download."
        ) from error


def _pool_embedding(value, pooling: str) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("Embedding service returned an empty or invalid vector.")
    value = [
        item.tolist() if hasattr(item, "tolist") else item
        for item in value
    ]

    while isinstance(value, (list, tuple)) and len(value) == 1 and isinstance(value[0], (list, tuple)):
        value = value[0]
        if hasattr(value, "tolist"):
            value = value.tolist()

    if value and isinstance(value[0], (int, float)):
        return [float(item) for item in value]
    if not all(isinstance(token, (list, tuple)) for token in value):
        raise ValueError("Embedding service returned an unsupported vector format.")
    token_vectors = [[float(item) for item in token] for token in value]
    if not token_vectors or len({len(token) for token in token_vectors}) != 1:
        raise ValueError("Embedding service returned inconsistent token vector dimensions.")
    if pooling == "cls":
        return token_vectors[0]
    if pooling == "last_token":
        return token_vectors[-1]
    return [
        sum(token[index] for token in token_vectors) / len(token_vectors)
        for index in range(len(token_vectors[0]))
    ]


def _embedding_batch(payload, expected_count: int, pooling: str) -> list[list[float]]:
    if isinstance(payload, dict):
        for key in ("embeddings", "embedding", "outputs", "output", "vectors"):
            if key in payload:
                payload = payload[key]
                break
        else:
            raise ValueError("Embedding API response did not contain embeddings.")
    if hasattr(payload, "tolist"):
        payload = payload.tolist()
    if not isinstance(payload, (list, tuple)):
        raise ValueError("Embedding API returned an unsupported response format.")

    if expected_count == 1:
        vectors = [_pool_embedding(payload, pooling)]
    elif len(payload) == expected_count:
        vectors = [_pool_embedding(item, pooling) for item in payload]
    else:
        raise ValueError(
            f"Embedding API returned {len(payload)} vectors for {expected_count} input texts."
        )
    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1:
        raise ValueError("Embedding API returned vectors with different dimensions.")
    return vectors


def _normalise_vectors(vectors: list[list[float]], normalize: bool) -> list[list[float]]:
    if not normalize:
        return vectors
    normalized = []
    for vector in vectors:
        norm = math.sqrt(sum(value * value for value in vector))
        if not norm:
            raise ValueError("Embedding model returned a zero vector; cannot normalize it.")
        normalized.append([value / norm for value in vector])
    return normalized


def _provider_headers(dataset: ApiDatasetConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token_name = dataset.embedding_api_key_env
    if token_name:
        token = os.getenv(token_name)
        if not token:
            raise ValueError(f"Required embedding API key environment variable '{token_name}' is not set.")
        prefix = "Bearer "
        headers["Authorization"] = (
            token if token.lower().startswith(prefix.lower()) else prefix + token
        )
    return headers


def _embedding_url(dataset: ApiDatasetConfig) -> str:
    if dataset.embedding_api_url:
        return dataset.embedding_api_url.format(model=dataset.embedding_model)
    return DEFAULT_OLLAMA_URL


def _vectors_once(texts: list[str], dataset: ApiDatasetConfig) -> list[list[float]]:
    purpose_prefix = dataset.document_prefix if dataset.mode == "text" else dataset.query_prefix
    inputs = [f"{purpose_prefix}{text}" for text in texts]
    if dataset.embedding_provider == "local":
        if dataset.embedding_model == DEFAULT_EMBEDDING_MODEL:
            raw_vectors = local_embedding_function()(inputs)
            vectors = _embedding_batch(raw_vectors, len(inputs), pooling="mean")
        else:
            model = _load_embedding_model(dataset.embedding_model)
            raw_vectors = list(model.embed(inputs))
            vectors = _embedding_batch(raw_vectors, len(inputs), pooling=dataset.pooling)
    else:
        payload = {"model": dataset.embedding_model, "input": inputs}
        response = requests.post(
            _embedding_url(dataset),
            headers=_provider_headers(dataset),
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        vectors = _embedding_batch(response.json(), len(inputs), pooling=dataset.pooling)

    if any(not math.isfinite(value) for vector in vectors for value in vector):
        raise ValueError(f"Embedding provider returned non-finite values for '{dataset.embedding_model}'.")
    return _normalise_vectors(vectors, dataset.normalize_embeddings)


def _vectors(texts: list[str], dataset: ApiDatasetConfig | None = None) -> list[list[float]]:
    if not texts:
        return []
    if dataset is None:
        raw_vectors = local_embedding_function()(texts)
        return _embedding_batch(raw_vectors, len(texts), pooling="mean")

    batch_size = 32
    vectors = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(_vectors_once(texts[start:start + batch_size], dataset))
    return vectors


def _chroma_client(database: VectorDatabaseConfig, api_key_env: str | None):
    from urllib.parse import urlsplit

    parsed = urlsplit(database.url)
    return chromadb.HttpClient(
        host=parsed.hostname,
        port=parsed.port or (443 if parsed.scheme == "https" else 8000),
        ssl=parsed.scheme == "https",
        headers=_headers(database, api_key_env),
        tenant=database.tenant or "default_tenant",
        database=database.database or "default_database",
    )


def _write_documents(
    dataset: ApiDatasetConfig,
    documents: list[tuple[str, str, str]],
) -> int:
    database = dataset.database
    chroma_collection = None
    if database.type == "chroma":
        chroma_collection = _chroma_client(database, dataset.api_key_env).get_or_create_collection(
            name=database.collection
        )

    for start in range(0, len(documents), 100):
        batch = documents[start:start + 100]
        ids = [item[0] for item in batch]
        titles = [item[1] for item in batch]
        texts = [item[2] for item in batch]
        vectors = _vectors(texts, dataset)
        metadata = [
            {"title": title, "source": dataset.data_url or dataset.id}
            for title in titles
        ]

        if database.type == "chroma":
            chroma_collection.upsert(
                ids=ids,
                documents=texts,
                metadatas=metadata,
                embeddings=vectors,
            )
        elif database.type == "pinecone":
            response = requests.post(
                f"{database.url.rstrip('/')}/vectors/upsert",
                headers=_headers(database, dataset.api_key_env),
                json={
                    "namespace": database.namespace or "",
                    "vectors": [
                        {
                            "id": identifier,
                            "values": vector,
                            "metadata": {**meta, database.text_property: text},
                        }
                        for identifier, vector, meta, text in zip(ids, vectors, metadata, texts)
                    ],
                },
                timeout=60,
            )
            response.raise_for_status()
        else:
            headers = _headers(database, dataset.api_key_env)
            for identifier, vector, title, text in zip(ids, vectors, titles, texts):
                object_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identifier))
                payload = {
                    "class": database.collection,
                    "id": object_id,
                    "properties": {
                        database.text_property: text,
                        database.title_property: title,
                    },
                    "vector": vector,
                }
                response = requests.put(
                    f"{database.url.rstrip('/')}/v1/objects/{database.collection}/{object_id}",
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
                if response.status_code == 404:
                    response = requests.post(
                        f"{database.url.rstrip('/')}/v1/objects",
                        headers=headers,
                        json=payload,
                        timeout=30,
                    )
                response.raise_for_status()
    return len(documents)


def index_text_dataset(dataset: ApiDatasetConfig) -> int:
    if dataset.mode != "text":
        raise ValueError(f"API dataset '{dataset.id}' is pre-embedded and does not need indexing.")
    documents = fetch_text_documents(dataset)
    return _write_documents(dataset, documents)


def _distance_score(distance: float | None) -> float:
    return 1 / (1 + max(float(distance), 0.0)) if distance is not None else 0.0


def _query_chroma(dataset: ApiDatasetConfig, vector: list[float], limit: int) -> list[dict]:
    collection = _chroma_client(dataset.database, dataset.api_key_env).get_collection(
        name=dataset.database.collection
    )
    response = collection.query(
        query_embeddings=[vector],
        n_results=limit,
        include=["documents", "metadatas", "distances"],
    )
    documents = response["documents"][0]
    metadatas = response["metadatas"][0]
    distances = response.get("distances", [[]])[0]
    if not distances:
        distances = [0.0] * len(documents)
    return [
        {
            "text": text or "",
            "metadata": metadata or {},
            "score": _distance_score(distance),
        }
        for text, metadata, distance in zip(documents, metadatas, distances)
    ]


def _query_pinecone(dataset: ApiDatasetConfig, vector: list[float], limit: int) -> list[dict]:
    database = dataset.database
    response = requests.post(
        f"{database.url.rstrip('/')}/query",
        headers=_headers(database, dataset.api_key_env),
        json={
            "namespace": database.namespace or "",
            "vector": vector,
            "topK": limit,
            "includeMetadata": True,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
        raise ValueError("Pinecone returned a response without a matches list.")
    matches = payload["matches"]
    return [
        {
            "text": (match.get("metadata") or {}).get(database.text_property, ""),
            "metadata": match.get("metadata") or {},
            "score": float(match.get("score", 0.0)),
        }
        for match in matches
        if isinstance(match, dict)
    ]


def _query_weaviate(dataset: ApiDatasetConfig, vector: list[float], limit: int) -> list[dict]:
    database = dataset.database
    vector_literal = json.dumps(vector, separators=(",", ":"))
    query = (
        "{ Get { "
        f"{database.collection}(nearVector: {{vector: {vector_literal}}}, limit: {limit}) "
        f"{{ {database.text_property} {database.title_property} _additional {{ distance }} }}"
        " } }"
    )
    response = requests.post(
        f"{database.url.rstrip('/')}/v1/graphql",
        headers=_headers(database, dataset.api_key_env),
        json={"query": query},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise ValueError(f"Weaviate query failed: {payload['errors']}")
    records = payload.get("data", {}).get("Get", {}).get(database.collection, [])
    return [
        {
            "text": record.get(database.text_property, ""),
            "metadata": {"title": record.get(database.title_property, dataset.name)},
            "score": _distance_score(
                (record.get("_additional") or {}).get("distance")
            ),
        }
        for record in records
        if isinstance(record, dict)
    ]


def query_api_dataset(dataset: ApiDatasetConfig, prompt: str, limit: int = 5) -> list[dict]:
    vector = _vectors([prompt], dataset)[0]
    if dataset.database.type == "chroma":
        results = _query_chroma(dataset, vector, limit)
    elif dataset.database.type == "pinecone":
        results = _query_pinecone(dataset, vector, limit)
    else:
        results = _query_weaviate(dataset, vector, limit)
    return [
        result
        for result in results
        if isinstance(result.get("text"), str) and result["text"].strip()
    ]
