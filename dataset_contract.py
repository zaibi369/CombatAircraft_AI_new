import re
import unicodedata
from datetime import datetime, timezone
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

SourceType = Literal["LOCAL", "ONLINE_API"]
DataType = Literal["TEXT", "EMBEDDED", "PAGES"]
DatasetStatus = Literal["PENDING", "PROCESSING", "READY", "FAILED"]
PageType = Literal["SINGLE", "DOUBLE"]

SOURCE_TYPES = get_args(SourceType)
DATA_TYPES = get_args(DataType)
DATASET_STATUSES = get_args(DatasetStatus)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class DatasetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    source_type: SourceType
    data_type: DataType
    scenario: str = Field(min_length=1, max_length=500)
    status: DatasetStatus
    created_at: str = Field(min_length=1, max_length=64)
    updated_at: str = Field(min_length=1, max_length=64)
    metadata: dict = Field(default_factory=dict)
    storage_location: str = Field(min_length=1, max_length=4000)
    page_type: PageType | None = None
    source_path: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)
    page_count: int | None = Field(default=None, ge=0)
    ocr_engine: str | None = Field(default=None, max_length=100)
    processing_status: DatasetStatus | None = None
    api_source_name: str | None = Field(default=None, max_length=200)
    retrieval_metadata: dict | None = None
    embedding_model: str | None = Field(default=None, max_length=200)
    embedding_dimensions: int | None = Field(default=None, gt=0)
    vector_format: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_source_metadata(self):
        if self.source_type == "ONLINE_API":
            if not self.api_source_name or not self.source_url:
                raise ValueError("Online API datasets require api_source_name and source_url.")
            if self.retrieval_metadata is None:
                raise ValueError("Online API datasets require retrieval_metadata.")
        if self.data_type == "PAGES":
            if not self.page_type or not self.ocr_engine or self.page_count is None:
                raise ValueError("Page datasets require page_type, page_count, and ocr_engine.")
            if self.processing_status is None:
                raise ValueError("Page datasets require processing_status.")
            if self.source_type == "LOCAL" and not self.source_path:
                raise ValueError("Local page datasets require source_path.")
            if self.source_type == "ONLINE_API" and not self.source_url:
                raise ValueError("Online page datasets require source_url.")
        if self.data_type == "EMBEDDED":
            if not self.embedding_model or self.embedding_dimensions is None or not self.vector_format:
                raise ValueError(
                    "Embedded datasets require embedding_model, embedding_dimensions, and vector_format."
                )
        return self


def automatic_name(candidate: str, text: str = "") -> str:
    candidate = unicodedata.normalize("NFC", candidate)
    candidate = re.sub(r"[ \t\f\v]+", " ", candidate).strip().split("\n", 1)[0]
    if candidate.lower() in {"dataset", "new dataset", "my text dataset", "text", "data"}:
        candidate = ""
    if not candidate:
        candidate = " ".join(text.split()[:6])
    candidate = re.sub(r"(?i)\.(txt|md|pdf|docx?|csv|json)$", "", candidate)
    candidate = re.sub(r"[^A-Za-z0-9]+", "_", candidate).strip("_")
    if not candidate or candidate.lower() in {"dataset", "new", "text", "data"}:
        candidate = "Project_Document"
    return candidate[:80].strip("_") or "Project_Document"


def _legacy_record(record: dict) -> dict:
    value = dict(record)
    metadata = dict(value.get("metadata") or {})
    metadata.update({
        key: item
        for key, item in value.items()
        if key not in {
            "dataset_id", "id", "dataset_name", "name", "source", "source_type",
            "type", "data_type", "scope", "scenario", "status", "created_at",
            "updated_at", "metadata", "storage_location", "origin",
            "indexed", "api_name", "api_source_name",
            "endpoint", "source_url", "folder", "source_path", "page_type",
            "page_count", "ocr_engine", "processing_status", "embedding_model",
            "embedding_dimensions", "vector_format", "retrieval_metadata",
        }
    })
    scope = str(value.get("source_type", value.get("scope", "LOCAL"))).strip().upper()
    if scope in {"API", "ONLINE_API"}:
        scope = "ONLINE_API"
    elif scope != "LOCAL":
        raise ValueError(
            f"Unsupported dataset source_type '{scope}'. Expected LOCAL or ONLINE_API."
        )
    data_type = value.get("data_type", value.get("type", value.get("dataset_type", "TEXT")))
    data_type = str(data_type).upper()
    data_type = "EMBEDDED" if data_type == "PREEMBEDDED" else data_type
    dataset_id = value.get("id", value.get("dataset_id"))
    name = value.get("name", value.get("dataset_name", dataset_id))
    source = value.get(
        "source_url",
        value.get("source_path", value.get("source", metadata.get("source", "legacy-catalog"))),
    )
    if scope == "ONLINE_API":
        value.setdefault("api_source_name", value.get("api_name") or name or "Online API")
        value.setdefault("source_url", value.get("endpoint") or source)
        value.setdefault("retrieval_metadata", {})
    if data_type == "PAGES":
        value["page_type"] = str(value.get("page_type", "SINGLE")).upper()
        value.setdefault("page_count", value.get("items", 0))
        value.setdefault("ocr_engine", "PaddleOCR")
        value.setdefault("processing_status", "READY")
        if scope == "LOCAL":
            value.setdefault("source_path", value.get("folder") or source)
        else:
            value.setdefault("source_url", value.get("endpoint") or source)
    if data_type == "EMBEDDED":
        value.setdefault("embedding_model", "all-MiniLM-L6-v2")
        value.setdefault("embedding_dimensions", metadata.get("embedding_dimensions", 384))
        value.setdefault("vector_format", metadata.get("vector_format", "float32[]"))
    created = value.get("created_at") or utc_timestamp()
    status = value.get("status") or ("READY" if value.get("indexed", True) else "PENDING")
    canonical = {
        "id": dataset_id,
        "name": name,
        "source_type": scope,
        "data_type": data_type,
        "scenario": value.get("scenario") or "General reference",
        "status": status,
        "created_at": created,
        "updated_at": value.get("updated_at") or created,
        "metadata": metadata,
        "storage_location": value.get("storage_location") or metadata.get("storage_location")
        or (f"external:{value.get('database_type', 'vector')}:{value.get('database_collection', name)}"
            if scope == "ONLINE_API" and value.get("mode")
            else f"chroma:{metadata.get('collection', value.get('collection', dataset_id))}"),
        "source_path": value.get("source_path"),
        "source_url": value.get("source_url"),
        "page_type": value.get("page_type"),
        "page_count": value.get("page_count"),
        "ocr_engine": value.get("ocr_engine"),
        "processing_status": value.get("processing_status"),
        "api_source_name": value.get("api_source_name"),
        "retrieval_metadata": value.get("retrieval_metadata"),
        "embedding_model": value.get("embedding_model"),
        "embedding_dimensions": value.get("embedding_dimensions"),
        "vector_format": value.get("vector_format"),
    }
    return DatasetRecord.model_validate(canonical).model_dump(exclude_none=True)


def dataset_record_response(record: DatasetRecord | dict) -> dict:
    canonical = _legacy_record(
        record.model_dump(exclude_none=True)
        if isinstance(record, DatasetRecord)
        else dict(record)
    )
    metadata = canonical["metadata"]
    source = canonical.get("source_url") or canonical.get("source_path") or metadata.get("source", "")
    data_type = canonical["data_type"].lower()
    scope = "api" if canonical["source_type"] == "ONLINE_API" else "local"
    response = {
        **canonical,
        "dataset_id": canonical["id"],
        "dataset_name": canonical["name"],
        "scope": scope,
        "type": data_type,
        "origin": f"{scope}_{data_type}",
        "source": source,
        "items": metadata.get("items", canonical.get("page_count", 0)),
        "indexed": canonical["status"] == "READY",
    }
    if "mode" in metadata:
        response["mode"] = metadata["mode"]
    if "collection" in metadata:
        response["collection"] = metadata["collection"]
    if "database_type" in metadata:
        response["database_type"] = metadata["database_type"]
    if "database_collection" in metadata:
        response["database_collection"] = metadata["database_collection"]
    if canonical.get("api_source_name") is not None:
        response["api_name"] = canonical["api_source_name"]
    if canonical.get("source_url") is not None:
        response["endpoint"] = canonical["source_url"]
    if canonical.get("source_path") is not None:
        response["folder"] = canonical["source_path"]
    return response


def canonical_dataset_record(record: dict, dataset_id: str | None = None) -> dict:
    normalized = dict(record)
    if dataset_id is not None and "id" not in normalized and "dataset_id" not in normalized:
        normalized["dataset_id"] = dataset_id
    canonical = _legacy_record(normalized)
    if dataset_id is not None and canonical["id"] != dataset_id:
        raise ValueError(
            f"Catalog key '{dataset_id}' does not match dataset id '{canonical['id']}'."
        )
    return canonical


def normalize_catalog_record(dataset_id: str, record: dict) -> dict:
    return dataset_record_response(canonical_dataset_record(record, dataset_id))
