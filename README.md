# Grounded Local AI

This project is a FastAPI-based AI assistant and dataset ingestion app for grounded retrieval, local dataset workflows, OCR-assisted ingestion, and web-search augmented answers.

## Core runtime

- Python app entrypoint: `server.py`
- API and dataset logic: `dataset_store.py`, `dataset_registry.py`, `api_dataset_registry.py`
- Local model endpoint is configured via environment variables
- Local vector storage defaults to a persistent Chroma database under `aircraft_vector_db_clean`

## Local development

1. Copy `.env.example` to `.env` and fill in secrets.
2. Install dependencies from `requirements.txt`.
3. Start the app with uvicorn or your normal local runtime.
4. Point `CHAT_URL` at an OpenAI-compatible local model server when using local inference.

## Deployment-friendly configuration

The app is structured to support both local testing and remote deployment by using environment variables instead of hard-coded endpoints:

- `CHAT_URL`
- `CHAT_MODEL`
- `CHAT_API_KEY`
- `VECTOR_DB_PATH`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `SEARCH_PROVIDER`

This keeps the same app easier to run locally and easier to point at cloud-backed storage or remote model providers.

## Clean repo baseline

Before pushing to GitHub, keep only the source, config templates, docs, and tests. Ignore generated runtime artifacts such as:

- vector databases
- the local model weights
- `.venv` and other environment folders
- OCR/temp output
- Python caches and local upload data

## Dockerized deployment

A simple container runtime is provided for online hosting:

```bash
docker compose up --build
```

This keeps the app accessible without relying on your laptop being online. The same app can still run locally by using `.env` values for a dev configuration.

## Important note

Large generated data directories, models, virtual environments, and caches are intentionally ignored by the repo and should not be committed as source.
