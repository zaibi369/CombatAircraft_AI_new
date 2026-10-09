# Project architecture

## Canonical boundaries

```text
DATA INGESTION
├── Local Text / Embedded / Pages
└── Online API Text / Embedded / Pages

PROCESSING
├── Extraction and OCR
├── Page detection/splitting
├── Cleaning and chunking
└── Embedding

DATA MANAGEMENT
├── Canonical dataset contract: dataset_contract.py
├── Unified selection registry: dataset_registry.py
├── Persistent local catalog and Chroma storage: dataset_store.py
└── Configured remote-vector adapter: api_dataset_registry.py

SEARCH
├── Intent classification and bounded evidence/completeness checks: query_intent.py
└── Query normalization, bounded research, provider fallback, parsing, retries, cache: web_search.py

UI
├── Local/Online import forms
├── Dataset selection and status
└── Chat: index.html → server.py
```

## Sources of truth and compatibility boundaries

- `DatasetRecord` in `dataset_contract.py` is the sole dataset contract:
  `id`, `name`, `source_type`, `data_type`, `scenario`, `status`, `created_at`,
  `updated_at`, `metadata`, and `storage_location`. It validates page provenance,
  API retrieval details, and embedded vector compatibility metadata. It also owns
  automatic naming and derives deprecated response aliases for existing clients.
- `dataset_store.py` is the sole persistent catalog for datasets imported through
  the application, including Online API imports. It validates and persists the
  canonical record before exposing a Chroma collection; older catalog records are
  normalized and migrated in place when loaded.
- `dataset_registry.py` is the single application-facing registry for Data
  Selection. It adapts persistent catalog records and configured remote-vector
  entries to the same canonical contract. Duplicate IDs across those sources are
  rejected instead of silently shadowing a dataset.
- `api_dataset_registry.py` remains the adapter for existing configured remote
  Chroma/Pinecone/Weaviate integrations. `api_datasets.json` describes connection
  and embedding settings; it is not a second persistent catalog for imported data.
- Existing HTTP routes and request shapes remain in `server.py`. Their responses
  include the canonical contract; legacy field aliases are derived by the contract
  adapter to preserve existing clients. Existing `/datasets/index`,
  `/datasets/import/*`, and `/ask` routes remain the integration surface.
- `page_ingestion.py` discovers local/temporary files and invokes `ocr_worker.py`.
  The worker owns PaddleOCR/PDF rendering and spread splitting. `web_search.py`
  stays separate from dataset retrieval and answer generation.

## Data flow

```text
Local Text UI → POST /datasets/import/text
  → validate/normalize → chunk → local embeddings → Chroma → catalog

Local Embedded UI → POST /datasets/import/embedded
  → validate passages/vectors/model → Chroma (supplied vectors) → catalog

Local Pages UI → POST /datasets/import/pages
  → discover local files → PaddleOCR/PDF rendering → normalize/chunk
  → local embeddings → Chroma → catalog

Online Text/Embedded/Pages UI → matching /datasets/import/* route
  → fetch and validate URL/API response → extract/OCR as needed
  → local embeddings or compatible supplied vectors → Chroma → catalog

Each successful import → dataset_contract.py validation
  → dataset_registry.py → GET /datasets/status → UI Data Selection

Configured remote vector source → api_datasets.json
  → api_dataset_registry.py adapter → dataset_registry.py → Data Selection

Question + selected dataset IDs → POST /ask
  → classify question; force live retrieval for market/currency/worldwide-list intents
  → bounded local/remote retrieval or primary provider with conditional Brave fallback
  → merge/deduplicate evidence → completeness-aware grounded prompt
  → local chat endpoint (default 127.0.0.1:8081)
```

Worldwide president lists issue at most five regional queries. Historical list
questions use at most two targeted queries. Provider errors are converted to an
insufficient-evidence state after configured fallback is attempted; current
financial answers do not use local Chroma as a substitute for missing live data.

## Conversation history

- The active conversation and archived chats are stored locally in the browser;
  conversations are not intentionally capped or truncated, and their content is
  kept in browser storage. Recent turns are also included as context in requests
  to the configured AI endpoint. Source links and generation statistics are
  retained with assistant replies. Browser storage still has a device-specific
  capacity, so storage errors are shown and a JSON backup can be downloaded.
- **New chat** offers Save, Discard, or Cancel. Saved chats can be reopened,
  searched, grouped by date, and individually deleted from the sidebar.
- Turning off conversation saving preserves existing chats and stops saving new
  changes; it does not delete the archive.
- Only one chat request runs at a time, and switching or deleting conversations
  is blocked while it is in flight. Failed requests remain visible as transient
  errors rather than being saved as assistant replies or sent back as model
  context; the prompt is restored for retry.
- The Data & Privacy settings can download a portable JSON backup of all saved
  chats plus the current conversation and restore a previous backup. Invalid
  backups are rejected without partially restoring their contents. Browser
  storage does not sync between devices. A single-chat export uses the same
  restore-compatible format.

Configured remote text datasets are indexed through the existing `/datasets/index`
route on first selection. Already-registered local catalog datasets are already
indexed and must not go through that remote-only indexing route.

## Runtime and dependencies

- The app/API runs in `.offline-venv`; its direct runtime dependencies are pinned
  in `requirements.txt`.
- OCR runs in a separate `.ocr-venv`; PaddleOCR/PaddlePaddle/PDF dependencies are
  pinned in `requirements-ocr.txt`. `OCR_PYTHON` can override the worker
  interpreter path. Book-page OCR uses PaddleOCR PP-OCRv6 medium text detection
  and recognition on CPU, with document-layout stages disabled and CPU threads
  capped for low-core-count systems. Long page imports have a four-hour worker
  timeout by default; set `OCR_TIMEOUT_SECONDS` to a positive number of seconds
  to adjust it for larger batches.
- Optional custom local embedding models use `requirements-embedding-models.txt`.
  The default local retrieval model does not require that optional package.
- The chat model server is a separate process. The bundled VS Code task starts
  llama.cpp on `127.0.0.1:8081`; the FastAPI app defaults to that endpoint via
  `CHAT_URL`.
- Web search uses external providers at runtime. `TAVILY_API_KEY` selects
  Tavily as primary; otherwise Bing is used. `BRAVE_SEARCH_API_KEY` enables
  conditional Brave fallback for failed or insufficient primary results. No
  live provider credentials are stored in the repository.

Install the matching pinned dependency set in each existing virtual environment
with `python -m pip install -r requirements.txt` or
`python -m pip install -r requirements-ocr.txt`; do not install both into one
environment.

## Repository inventory and legacy classification

### Active application path

`index.html`, `server.py`, `dataset_contract.py`, `dataset_store.py`,
`dataset_registry.py`, `api_dataset_registry.py`, `page_ingestion.py`,
`ocr_worker.py`, and `web_search.py` implement the current browser/API, contract,
storage, configured-remote-adapter, OCR, and web-search paths. The active tests
are under `tests/`.

### Legacy or separate files retained in place

- **REFERENCED LEGACY:** `ocr_processor.py` is still exposed by a VS Code task
  and its page-splitting helpers have tests. It is not the active API OCR worker.
- **REFERENCED LEGACY:** `build_db.py` imports `book_rag.py`; the latter has its
  own tests. Neither is imported by the active FastAPI ingestion path.
- **UNREFERENCED LEGACY:** `ollama_agent.py` is not imported or wired into the
  active web app; keep it for compatibility until its owner confirms removal.
- **UNKNOWN / SEPARATE:** `Banking_App.py`, `main.c`, `practice.html`, and
  `style.css` are not part of the active FastAPI routes. They are left untouched.
- **PRESERVED DATA:** `aircraft_vector_db`, `aircraft_vector_db_clean`, and
  `aircraft_vector_db_elon` contain Chroma collections. The inspected stores do
  not contain `dataset_catalog.json`; therefore those collections cannot be
  safely represented by the canonical dataset contract without deciding their
  source, type, scenario, and embedding compatibility. They were not modified or
  automatically registered. The active store path is
  `aircraft_vector_db_clean`, configured through `VECTOR_DB_PATH`.
- `book_images/`, extracted text files, and the bundled GGUF model are retained
  project data/assets and are not cleaned up by the app audit.

Git status could not be inspected in this environment because `git.exe` is not
available on the command path or the checked standard install locations. No
cleanup/reset/checkout operation was performed.

Do not delete or auto-migrate these legacy files/stores as a cleanup operation.
