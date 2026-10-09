import hashlib
import json
import math
import re
import threading
import unicodedata
from pathlib import Path
from typing import Callable

import chromadb
from app_config import VECTOR_DB_PATH
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from dataset_contract import (
    DATA_TYPES,
    SOURCE_TYPES,
    DatasetRecord,
    automatic_name,
    canonical_dataset_record,
    dataset_record_response,
    utc_timestamp,
)

BASE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = VECTOR_DB_PATH / "dataset_catalog.json"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
WORDS_PER_CHUNK = 120
CHUNK_OVERLAP = 24
_STORE_LOCK = threading.RLock()
_PERSISTENT_CLIENT_LOCK = threading.Lock()


def local_embedding_function():
    return DefaultEmbeddingFunction()


def persistent_vector_client(vector_db_path: Path | None = None):
    database_path = vector_db_path or VECTOR_DB_PATH
    with _PERSISTENT_CLIENT_LOCK:
        return chromadb.PersistentClient(path=str(database_path))


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\x00", " ")
    normalized = re.sub(r"[ \t\f\v]+", " ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def split_text(text: str) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + WORDS_PER_CHUNK, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def _catalog_path(vector_db_path: Path | None = None) -> Path:
    return (vector_db_path or VECTOR_DB_PATH) / "dataset_catalog.json"


def _trash_catalog_path(vector_db_path: Path | None = None) -> Path:
    return (vector_db_path or VECTOR_DB_PATH) / "dataset_trash.json"


def load_catalog(vector_db_path: Path | None = None) -> dict[str, dict]:
    catalog_path = _catalog_path(vector_db_path)
    if not catalog_path.exists():
        return {}
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read dataset catalog: {error}") from error
    if not isinstance(catalog, dict) or not isinstance(catalog.get("datasets"), dict):
        raise ValueError("Dataset catalog must contain a datasets object.")
    raw_datasets = catalog["datasets"]
    datasets = {}
    try:
        for dataset_id, record in raw_datasets.items():
            if not isinstance(dataset_id, str) or not isinstance(record, dict):
                raise ValueError("Every catalog dataset must be an object keyed by its ID.")
            datasets[dataset_id] = canonical_dataset_record(record, dataset_id)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Dataset catalog contains an invalid dataset record: {error}") from error
    if datasets != raw_datasets:
        save_catalog(datasets, vector_db_path)
    return datasets


def save_catalog(datasets: dict[str, dict], vector_db_path: Path | None = None) -> None:
    catalog_path = _catalog_path(vector_db_path)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = catalog_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps({"version": 1, "datasets": datasets}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary_path.replace(catalog_path)


def _load_trash(vector_db_path: Path | None = None) -> dict[str, dict]:
    trash_path = _trash_catalog_path(vector_db_path)
    if not trash_path.exists():
        return {}
    try:
        payload = json.loads(trash_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read dataset recycle bin: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("datasets"), dict):
        raise ValueError("Dataset recycle bin must contain a datasets object.")
    trashed = {}
    for dataset_id, entry in payload["datasets"].items():
        if not isinstance(dataset_id, str) or not isinstance(entry, dict):
            raise ValueError("Every recycle-bin entry must be an object keyed by dataset ID.")
        record = entry.get("record")
        trashed_at = entry.get("trashed_at")
        if not isinstance(record, dict) or not isinstance(trashed_at, str):
            raise ValueError(f"Recycle-bin entry '{dataset_id}' is invalid.")
        canonical = canonical_dataset_record(record, dataset_id)
        trashed[dataset_id] = {"record": canonical, "trashed_at": trashed_at}
    return trashed


def _save_trash(trash: dict[str, dict], vector_db_path: Path | None = None) -> None:
    trash_path = _trash_catalog_path(vector_db_path)
    trash_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = trash_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps({"version": 1, "datasets": trash}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary_path.replace(trash_path)


def list_trashed_datasets(vector_db_path: Path | None = None) -> list[dict]:
    with _STORE_LOCK:
        trash = _load_trash(vector_db_path)
        return [
            {**dataset_record_response(entry["record"]), "trashed_at": entry["trashed_at"]}
            for entry in trash.values()
        ]


def move_dataset_to_trash(dataset_id: str, vector_db_path: Path | None = None) -> dict:
    with _STORE_LOCK:
        catalog = load_catalog(vector_db_path)
        if dataset_id not in catalog:
            raise KeyError(dataset_id)
        trash = _load_trash(vector_db_path)
        if dataset_id in trash:
            raise ValueError(f"Dataset '{dataset_id}' is already in the recycle bin.")
        record = catalog.pop(dataset_id)
        trash[dataset_id] = {"record": record, "trashed_at": utc_timestamp()}
        _save_trash(trash, vector_db_path)
        try:
            save_catalog(catalog, vector_db_path)
        except OSError:
            del trash[dataset_id]
            _save_trash(trash, vector_db_path)
            raise
        return dataset_record_response(record)


def restore_dataset_from_trash(dataset_id: str, vector_db_path: Path | None = None) -> dict:
    with _STORE_LOCK:
        catalog = load_catalog(vector_db_path)
        trash = _load_trash(vector_db_path)
        entry = trash.get(dataset_id)
        if entry is None:
            raise KeyError(dataset_id)
        if dataset_id in catalog:
            raise ValueError(f"Dataset '{dataset_id}' already exists in the active catalog.")
        catalog[dataset_id] = entry["record"]
        save_catalog(catalog, vector_db_path)
        del trash[dataset_id]
        try:
            _save_trash(trash, vector_db_path)
        except OSError:
            del catalog[dataset_id]
            save_catalog(catalog, vector_db_path)
            raise
        return dataset_record_response(entry["record"])


def permanently_delete_trashed_dataset(
    dataset_id: str,
    vector_db_path: Path | None = None,
) -> None:
    with _STORE_LOCK:
        trash = _load_trash(vector_db_path)
        entry = trash.get(dataset_id)
        if entry is None:
            raise KeyError(dataset_id)

        record = entry["record"]
        collection_name = (record.get("metadata") or {}).get("collection")
        if collection_name:
            client = persistent_vector_client(vector_db_path)
            if collection_name in {collection.name for collection in client.list_collections()}:
                collection = client.get_collection(name=collection_name)
                collection_metadata = collection.metadata or {}
                collection_dataset_id = collection_metadata.get("dataset_id")
                if collection_dataset_id not in {None, dataset_id}:
                    raise ValueError(
                        f"Collection '{collection_name}' is not owned by dataset '{dataset_id}'."
                    )
                client.delete_collection(name=collection_name)

        del trash[dataset_id]
        _save_trash(trash, vector_db_path)


def _dataset_identity(source: str, data_type: str, payload: str) -> str:
    return hashlib.sha256(
        f"{data_type}\n{source.strip()}\n{payload}".encode("utf-8")
    ).hexdigest()


def _chroma_metadata(dataset: dict, passage: dict, index: int) -> dict:
    result = {
        "dataset_id": dataset["id"],
        "dataset_name": dataset["name"],
        "source": dataset["metadata"]["source"],
        "type": dataset["data_type"].lower(),
        "scenario": dataset["scenario"],
        "created_at": dataset["created_at"],
        "embedding_model": dataset["embedding_model"],
        "ordinal": index,
    }
    for key, value in (passage.get("metadata") or {}).items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        elif value is not None and not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"Passage metadata field '{key}' has an unsupported value.")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"Passage metadata field '{key}' must be finite.")
        result[f"source_{key}"] = "null" if value is None else value
    for key in ("page", "page_start", "page_end"):
        if key in passage:
            result[key] = passage[key]
    return result


def _store_dataset(
    *,
    dataset_name: str,
    source: str,
    data_type: str,
    scenario: str,
    passages: list[dict],
    embedding_model: str,
    vectors: list[list[float]] | None = None,
    extra_metadata: dict | None = None,
    vector_db_path: Path | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> dict:
    with _STORE_LOCK:
        return _store_dataset_locked(
            dataset_name=dataset_name,
            source=source,
            data_type=data_type,
            scenario=scenario,
            passages=passages,
            embedding_model=embedding_model,
            vectors=vectors,
            extra_metadata=extra_metadata,
            vector_db_path=vector_db_path,
            progress_callback=progress_callback,
        )


def _store_dataset_locked(
    *,
    dataset_name: str,
    source: str,
    data_type: str,
    scenario: str,
    passages: list[dict],
    embedding_model: str,
    vectors: list[list[float]] | None = None,
    extra_metadata: dict | None = None,
    vector_db_path: Path | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> dict:
    if not passages:
        raise ValueError("No usable text passages were provided.")
    normalized_passages = []
    for passage in passages:
        if not isinstance(passage, dict):
            raise ValueError("Each passage must be an object containing text.")
        passage_text = passage.get("text", "")
        if not isinstance(passage_text, str):
            raise ValueError("Passage text must be a string.")
        passage_metadata = passage.get("metadata") or {}
        if not isinstance(passage_metadata, dict):
            raise ValueError("Passage metadata must be an object.")
        if any(
            key in passage
            and (
                not isinstance(passage[key], (str, int, float, bool))
                or (isinstance(passage[key], float) and not math.isfinite(passage[key]))
            )
            for key in ("page", "page_start", "page_end")
        ):
            raise ValueError("Page metadata values must be strings or numbers.")
        text = normalize_text(passage_text)
        if text:
            normalized_passages.append({**passage, "metadata": passage_metadata, "text": text})
    if not normalized_passages:
        raise ValueError("No usable text passages were provided.")
    if vectors is not None:
        if len(vectors) != len(normalized_passages):
            raise ValueError("Each text passage must have exactly one embedding vector.")
        dimensions = set()
        for index, vector in enumerate(vectors):
            if not isinstance(vector, (list, tuple)) or not vector:
                raise ValueError(f"Embedding {index + 1} must be a non-empty numeric vector.")
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in vector
            ):
                raise ValueError(f"Embedding {index + 1} contains invalid numeric values.")
            dimensions.add(len(vector))
        if len(dimensions) != 1:
            raise ValueError("All embeddings must have the same dimensions.")
        if embedding_model != EMBEDDING_MODEL:
            raise ValueError(
                f"Embedding model '{embedding_model}' is incompatible with local retrieval; "
                f"expected '{EMBEDDING_MODEL}'."
            )
        if dimensions != {384}:
            raise ValueError("The local retrieval model requires 384-dimensional embeddings.")

    content_hash = hashlib.sha256(
        "\n".join(passage["text"] for passage in normalized_passages).encode("utf-8")
    ).hexdigest()
    supplied_metadata = dict(extra_metadata or {})
    legacy_scope = supplied_metadata.pop("scope", None)
    source_type = supplied_metadata.pop("source_type", None)
    if source_type is None:
        source_type = "ONLINE_API" if legacy_scope == "api" else "LOCAL"
    if source_type not in SOURCE_TYPES:
        raise ValueError("Source type must be LOCAL or ONLINE_API.")
    scope_value = "api" if source_type == "ONLINE_API" else "local"
    supplied_type = supplied_metadata.pop(
        "data_type",
        supplied_metadata.pop("dataset_type", data_type.upper()),
    )
    if str(supplied_type).upper() != data_type.upper():
        raise ValueError("Dataset type metadata must match the dataset type.")
    data_type_value = data_type.upper()
    fingerprint = _dataset_identity(f"{scope_value}:{source}", data_type, content_hash)
    catalog = load_catalog(vector_db_path)
    for dataset in catalog.values():
        old_metadata = dataset.get("metadata") or {}
        if old_metadata.get("fingerprint", dataset.get("fingerprint")) == fingerprint:
            raise FileExistsError(
                f"This source is already registered as "
                f"'{dataset.get('name', dataset.get('dataset_name', 'a dataset'))}'."
            )

    dataset_id = f"data_{fingerprint[:16]}"
    display_name = automatic_name(dataset_name, normalized_passages[0]["text"])
    existing_names = {
        str(dataset.get("name", dataset.get("dataset_name", ""))).casefold()
        for dataset in catalog.values()
    }
    base_name = display_name
    suffix = 2
    while display_name.casefold() in existing_names:
        display_name = f"{base_name[:72]}_{suffix:02d}"
        suffix += 1
    collection_name = f"source_{fingerprint[:28]}"
    database_path = vector_db_path or VECTOR_DB_PATH
    created_at = utc_timestamp()
    page_type = supplied_metadata.pop("page_type", None)
    page_count = supplied_metadata.pop("page_count", None)
    ocr_engine = supplied_metadata.pop("ocr_engine", None)
    processing_status = supplied_metadata.pop("processing_status", None)
    api_name = supplied_metadata.pop("api_name", None)
    endpoint = supplied_metadata.pop("endpoint", None)
    supplied_metadata.pop("folder", None)
    metadata = {
        **supplied_metadata,
        "source": source,
        "fingerprint": fingerprint,
        "collection": collection_name,
        "items": len(normalized_passages),
    }
    if api_name:
        metadata["retrieval_metadata"] = {
            "api_name": api_name,
            "endpoint": endpoint or source,
            **(metadata.get("retrieval_metadata") or {}),
        }
    if data_type_value == "EMBEDDED":
        metadata["embedding_dimensions"] = len(vectors[0])
        metadata["vector_format"] = "float32[]"
    record = DatasetRecord.model_validate({
        "id": dataset_id,
        "name": display_name,
        "source_type": source_type,
        "data_type": data_type_value,
        "scenario": normalize_text(scenario) or "General reference",
        "status": "READY",
        "created_at": created_at,
        "updated_at": created_at,
        "metadata": metadata,
        "storage_location": f"chroma://{database_path.resolve().as_posix()}#{collection_name}",
        "page_type": str(page_type).upper() if page_type else None,
        "source_path": source if source_type == "LOCAL" and data_type_value == "PAGES" else None,
        "source_url": source if source_type == "ONLINE_API" else None,
        "page_count": page_count,
        "ocr_engine": ocr_engine,
        "processing_status": processing_status or ("READY" if data_type_value == "PAGES" else None),
        "api_source_name": api_name,
        "retrieval_metadata": metadata.get("retrieval_metadata") if source_type == "ONLINE_API" else None,
        "embedding_model": embedding_model,
        "embedding_dimensions": len(vectors[0]) if vectors is not None else (
            384 if embedding_model == EMBEDDING_MODEL else None
        ),
        "vector_format": "float32[]" if data_type_value == "EMBEDDED" else None,
    }).model_dump(exclude_none=True)
    if data_type_value == "PAGES" and record["page_count"] is None:
        raise ValueError("Page imports must provide the number of processed pages.")
    metadata = record["metadata"]
    client = persistent_vector_client(database_path)
    collection = client.create_collection(
        name=collection_name,
        embedding_function=local_embedding_function(),
        metadata={"embedding_model": embedding_model, "dataset_id": dataset_id},
    )
    try:
        ids = [f"passage_{index:06d}" for index in range(len(normalized_passages))]
        documents = [passage["text"] for passage in normalized_passages]
        metadatas = [
            _chroma_metadata(record, passage, index)
            for index, passage in enumerate(normalized_passages)
        ]
        batch_size = 16
        total_passages = len(normalized_passages)
        for start in range(0, total_passages, batch_size):
            end = min(start + batch_size, total_passages)
            batch = {
                "ids": ids[start:end],
                "documents": documents[start:end],
                "metadatas": metadatas[start:end],
            }
            if vectors is None:
                collection.add(**batch)
            else:
                collection.add(embeddings=vectors[start:end], **batch)
            if progress_callback is not None:
                progress_callback(
                    "embedding" if vectors is None else "storing",
                    end,
                    total_passages,
                )
        if collection.count() != len(normalized_passages):
            raise ValueError("Stored passage count does not match the validated dataset.")
        catalog[dataset_id] = record
        save_catalog(catalog, database_path)
        if progress_callback is not None:
            progress_callback("saving", 1, 1)
    except Exception:
        client.delete_collection(collection_name)
        raise
    return dataset_record_response(record)


def store_text_dataset(
    *,
    name: str,
    source: str,
    source_type: str,
    data_type: str,
    scenario: str,
    text: str,
    embedding_model: str = EMBEDDING_MODEL,
    metadata: dict | None = None,
    vector_db_path: Path | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> dict:
    if data_type not in DATA_TYPES:
        raise ValueError("Data type must be TEXT, EMBEDDED, or PAGES.")
    cleaned_text = normalize_text(text)
    if len(cleaned_text) < 3:
        raise ValueError("Text is empty or too short to index.")
    passages = [{"text": chunk} for chunk in split_text(cleaned_text)]
    return _store_dataset(
        dataset_name=name,
        source=source,
        data_type=data_type.lower(),
        scenario=scenario,
        passages=passages,
        embedding_model=embedding_model,
        extra_metadata={**(metadata or {}), "source_type": source_type},
        vector_db_path=vector_db_path,
        progress_callback=progress_callback,
    )


def store_embedded_dataset(
    *,
    name: str,
    source: str,
    source_type: str,
    data_type: str,
    scenario: str,
    passages: list[dict],
    vectors: list[list[float]],
    embedding_model: str,
    metadata: dict | None = None,
    vector_db_path: Path | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> dict:
    if data_type != "EMBEDDED":
        raise ValueError("Precomputed vectors must use data_type EMBEDDED.")
    return _store_dataset(
        dataset_name=name,
        source=source,
        data_type="embedded",
        scenario=scenario,
        passages=passages,
        embedding_model=embedding_model,
        vectors=vectors,
        extra_metadata={**(metadata or {}), "source_type": source_type},
        vector_db_path=vector_db_path,
        progress_callback=progress_callback,
    )
