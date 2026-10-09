# Dataset ingestion and retrieval

The sidebar separates **Local Data** from **Online API Data**. Each group has
Text, Embedded, and Pages import flows; successfully validated imports are saved
to an isolated Chroma collection and added to Data Selection. Local and API
sources retain their own scope and metadata.

`dataset_contract.py` defines the shared dataset metadata and naming contract.
`dataset_registry.py` presents both catalog-backed imports and configured remote
vector datasets through the same Data Selection status shape. Imported datasets
are stored in the catalog managed by `dataset_store.py`; `api_datasets.json`
remains configuration for the remote vector adapter, not a competing import
catalog. See [ARCHITECTURE.md](./ARCHITECTURE.md) for subsystem boundaries.

The canonical record fields are `id`, `name`, `source_type` (`LOCAL` /
`ONLINE_API`), `data_type` (`TEXT` / `EMBEDDED` / `PAGES`), `scenario`, `status`,
`created_at`, `updated_at`, `metadata`, and `storage_location`. Page records also
carry page type/count, source, OCR engine, and processing status. API records carry
source name/URL and retrieval metadata. Embedded records carry model, dimensions,
and vector format.

Existing catalog entries are converted and persisted in the canonical shape on
load. Existing HTTP response aliases (`dataset_id`, `dataset_name`, lowercase
scope/type, `source`, and `indexed`) are derived for backward compatibility; new
clients should use the canonical fields.

Every registered dataset records its generated name, source, type, scenario,
creation time, embedding model, collection, and passage count. API sources also
record their endpoint and API name. Page sources record their path or URL, page
mode, and PaddleOCR engine. The UI displays the scope/type label and scenario
beside each selectable dataset.

## Local imports

- **Text** accepts pasted text or `.txt` / `.md` files. Text is normalized,
  chunked, embedded with `all-MiniLM-L6-v2`, validated, and registered.
- **Embedded** accepts JSON with `embedding_model`, `passages` (or `documents`),
  and `embeddings` (or `vectors`). Every passage must contain text; each vector
  must be finite, have 384 dimensions, and be compatible with
  `all-MiniLM-L6-v2`. Valid vectors are stored directly without re-embedding.
- **Pages** accepts a path to an image, PDF, or directory. PaddleOCR's layout
  pipeline extracts page text and preserves its detected reading order. Double
  Page mode detects the likely center gutter from page content and falls back
  to a centered split only when no clear gutter is present. A failed page stops
  the import rather than silently registering partial text.

The local path is interpreted by the machine running the app. When the browser
and server are on different machines, the path must be accessible to the
server.

## Online API imports

- **Text** fetches a URL and extracts records from JSON `rows`, `documents`,
  `records`, `data`, `items`, or `results` collections. Recognized text fields
  include `text`, `content`, `passage`, `context`, and question/answer pairs.
  Plain text and visible HTML text are also accepted.
- **Embedded** fetches JSON containing `passages` / `documents` and
  `embeddings` / `vectors`, with an optional `embedding_model`. The vectors are
  stored unchanged after the same local compatibility checks as imported local
  vectors.
- **Pages / API Link** fetches a web page, image, or PDF. HTML is parsed in
  document order; image/PDF content is processed through PaddleOCR. A URL/API
  key is sent only for that request and is not stored.

Online downloads are limited to 50 MB. HTTP failures, invalid responses,
unsupported document formats, duplicate datasets, and incompatible vectors are
reported and do not appear in Data Selection. API keys are sent as Bearer
tokens unless the value already begins with `Bearer `.

## Embedding compatibility

This app's local retrieval query encoder is `all-MiniLM-L6-v2` (384 dimensions).
Precomputed vectors from another model or dimension cannot be queried correctly
by that encoder and are rejected rather than silently re-embedded or
misrepresented. Text and page imports use the app's existing local embedding
function.

## Configured external vector APIs

Optional preconfigured vector databases can still be declared in
`api_datasets.json`; `api_datasets.schema.json` provides editor validation.
Each entry has a unique ID, name, mode (`text` or `preembedded`), database
destination, and embedding provider (`local` or `ollama`). Text entries are
indexed on first selection. Credentials are read from environment variables,
never emitted in the status endpoint. Keep each dataset in a distinct
collection or namespace.

## Selecting and asking

Select one or more entries under Local Datasets and Online API Datasets. The
chat retrieves passages from each selected dataset, ranks them by relevance,
and grounds its response in the retrieved evidence. Local and mixed search
require at least one selected dataset; Web only does not.

Managed imported datasets have a small remove button in Data Selection. It
moves the dataset to the Recycle bin without deleting its vectors; restore it
there if needed. Permanent deletion is available from the Recycle bin and
removes only that dataset's Chroma collection. Configured remote API entries
cannot be removed from this app because they are defined in `api_datasets.json`.
Text, pre-embedded vector, and page imports show a live progress bar. Page
imports report OCR pages completed, followed by embedding and catalog-save
progress; the progress does not require keeping the import request open.

## Live web search

Choose **Web only** or **Local + web** beside Send. Search questions are
reduced to concise, focused terms before being sent to the provider. A few
high-confidence common misspellings are corrected for intent classification
and search (for example, “naem” to “name” and “exhcange ratebetween” to
“exchange rate between”); original user wording remains unchanged. In a
currency-conversion context, “PKR to US” is interpreted as PKR to USD. If
`TAVILY_API_KEY` is configured, the app uses Tavily; otherwise it uses Bing
results through the Jina Reader text endpoint. Results are parsed,
relevance-checked, deduplicated, validated as HTTPS links, and known
authoritative domains are ranked ahead of general sites. List, multi-part, and
research questions retrieve a larger but bounded set of evidence passages than
single-fact questions. Current-market and currency-rate questions are forced to
live web retrieval and never fall back to stale local Chroma data. Worldwide
country-president lists use five bounded regional searches and report region
coverage; historical president lists use a small set of targeted searches.
Matching excerpts
are extracted from up to three authoritative result pages when available;
failed page retrieval falls back to the provider's search snippet. Successful
searches are cached for two minutes; temporary network, rate-limit, and server
failures receive one bounded retry. If the primary provider fails or returns
too few useful distinct results for a multi-item query, Brave Search is tried
only when `BRAVE_SEARCH_API_KEY` is configured in the server environment. A
provider exception, timeout, empty response, or invalid result set is treated
as insufficient evidence, not as a completed search. Current financial
questions with evidence missing a requested currency/entity stop before Qwen
instead of generating a guess. A single official historical-list page is
sufficient only when its content covers the requested years and contains
multiple named office holders. Structured currency payloads (`base_code`,
`conversion_rates`/`rates`, and update time) are normalized into explicit
rate evidence and included in the Qwen context; unrelated snippets are not
treated as a numeric exchange rate. Evidence-gate logs include provider,
source title/URL, snippet, score, result count, and the sufficiency decision.
These diagnostics are emitted at INFO level by the running app.
The key is never sent to the browser. Results are merged by source URL and
near-identical excerpts from the same domain are suppressed. When all online
search providers fail, selected local datasets are used as a fallback if
available; otherwise the API reports a controlled failure instead of passing
fabricated evidence to the answer model. Response metrics include intent,
retrieval, provider, fallback, model, and total timings where available.
