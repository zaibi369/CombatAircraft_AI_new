from pathlib import Path

from api_dataset_registry import (
    API_DATASETS_PATH,
    ApiDatasetConfig,
    dataset_signature,
    load_registry,
)
from dataset_contract import (
    DATA_TYPES,
    SOURCE_TYPES,
    dataset_record_response,
    normalize_catalog_record,
    utc_timestamp,
)
from dataset_store import VECTOR_DB_PATH, load_catalog


def _configured_dataset_record(
    dataset: ApiDatasetConfig,
    prepared_datasets: dict[str, tuple[str, int]],
) -> dict:
    prepared = prepared_datasets.get(dataset.id)
    signature = dataset_signature(dataset)
    indexed = dataset.mode == "preembedded" or bool(
        prepared and prepared[0] == signature
    )
    source = dataset.data_url or dataset.database.url
    data_type = "EMBEDDED" if dataset.mode == "preembedded" else "TEXT"
    now = utc_timestamp()
    record = {
        "id": dataset.id,
        "name": dataset.name,
        "source_type": "ONLINE_API",
        "data_type": data_type,
        "scenario": "Configured API dataset",
        "status": "READY" if indexed else "PENDING",
        "created_at": now,
        "updated_at": now,
        "metadata": {
            "mode": dataset.mode,
            "embedding_provider": dataset.embedding_provider,
            "database_type": dataset.database.type,
            "database_collection": dataset.database.collection,
            "items": prepared[1] if indexed and prepared else 0,
        },
        "storage_location": (
            f"{dataset.database.type}://{dataset.database.url.rstrip('/')}/"
            f"{dataset.database.collection}"
        ),
        "api_source_name": dataset.name,
        "source_url": source,
        "retrieval_metadata": {
            "data_url": dataset.data_url,
            "database_type": dataset.database.type,
            "database_url": dataset.database.url,
            "collection": dataset.database.collection,
        },
        "embedding_model": dataset.embedding_model,
    }
    if dataset.mode == "preembedded":
        dimensions = getattr(dataset, "embedding_dimensions", None)
        if not dimensions:
            raise ValueError(
                f"Configured embedded dataset '{dataset.id}' must declare embedding_dimensions."
            )
        record["embedding_dimensions"] = dimensions
        record["vector_format"] = "float32[]"
    return dataset_record_response(record)


def list_datasets(
    *,
    prepared_datasets: dict[str, tuple[str, int]],
    vector_db_path: Path = VECTOR_DB_PATH,
    api_datasets_path: Path = API_DATASETS_PATH,
) -> dict:
    datasets = {
        dataset_id: normalize_catalog_record(dataset_id, dataset)
        for dataset_id, dataset in load_catalog(vector_db_path).items()
    }
    for configured_dataset in load_registry(api_datasets_path):
        if configured_dataset.id in datasets:
            raise ValueError(
                f"Dataset ID '{configured_dataset.id}' is used by both the local catalog "
                "and the configured API registry."
            )
        datasets[configured_dataset.id] = _configured_dataset_record(
            configured_dataset,
            prepared_datasets,
        )

    scope_groups = {
        "LOCAL": "local",
        "ONLINE_API": "api",
    }
    groups = {
        scope_groups[scope]: {kind.lower(): [] for kind in DATA_TYPES}
        for scope in SOURCE_TYPES
    }
    for dataset in datasets.values():
        scope = "api" if dataset["source_type"] == "ONLINE_API" else "local"
        kind = dataset["data_type"].lower()
        groups[scope][kind].append(dataset)
    return {"datasets": datasets, "groups": groups}
