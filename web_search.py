import base64
import html
import logging
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse

import requests

from query_intent import (
    CURRENT_WEB,
    LARGE_LIST,
    LIST,
    LIVE_MARKET,
    MULTI_PART,
    RESEARCH_WEB,
    classify_question,
    normalize_common_query_typos,
)

BING_READER_URL = "https://r.jina.ai/http://www.bing.com/search"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
SEARCH_CACHE_TTL_SECONDS = 120
SEARCH_CACHE_MAX_ENTRIES = 128
SEARCH_MAX_ATTEMPTS = 2
SEARCH_TIMEOUT_SECONDS = 12
LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    _search_log_handler = logging.StreamHandler()
    _search_log_handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(_search_log_handler)
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False
_search_cache: dict[
    tuple[str, str, int],
    tuple[float, list[dict[str, str]], dict[str, object]],
] = {}
_search_cache_lock = threading.Lock()
AUTHORITATIVE_DOMAINS = {
    "reuters.com": 5,
    "apnews.com": 5,
    "bloomberg.com": 5,
    "forbes.com": 4,
    "bbc.com": 4,
    "ft.com": 4,
    "wsj.com": 4,
    "nytimes.com": 4,
    "wikipedia.org": 2,
    "python-requests.org": 5,
    "xe.com": 4,
    "exchange-rates.org": 4,
}
STOP_WORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does",
    "for", "from", "give", "how", "i", "in", "is", "it", "latest", "me", "of", "on",
    "or", "please", "show", "tell", "the", "their", "them", "there", "these", "this",
    "to", "today", "was", "what", "when", "where", "which", "who", "why", "with",
    "current", "report", "reported", "handling", "list", "enumerate", "name", "names",
    "all", "each", "every", "main", "different", "various", "types", "type", "kinds",
    "kind", "examples", "items", "include", "provide", "identify", "were",
    "library", "libraries", "behavior", "behaviors", "behaviour", "behaviours",
}
CURRENCY_ALIASES = {
    "CHF": ("CHF", "Swiss franc", "Swiss francs", "Swiss currency"),
    "PKR": ("PKR", "Pakistani rupee", "Pakistani rupees"),
    "USD": ("USD", "US dollar", "US dollars", "American dollar"),
    "EUR": ("EUR", "euro", "euros"),
    "GBP": ("GBP", "British pound", "pound sterling"),
    "JPY": ("JPY", "Japanese yen", "yen"),
    "INR": ("INR", "Indian rupee", "Indian rupees"),
    "CAD": ("CAD", "Canadian dollar", "Canadian dollars"),
    "AUD": ("AUD", "Australian dollar", "Australian dollars"),
    "CNY": ("CNY", "Chinese yuan", "yuan", "renminbi"),
    "AED": ("AED", "UAE dirham", "Emirati dirham"),
    "SAR": ("SAR", "Saudi riyal", "Saudi riyals"),
}


def _clean(value: str | None) -> str:
    if not isinstance(value, str) or not value:
        return ""
    value = html.unescape(re.sub(r"<[^>]*>", " ", value))
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"[*_`#>]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(value: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", value.lower()))
    normalized = set()
    for token in tokens:
        if token.endswith("ies") and len(token) > 5:
            token = token[:-3] + "y"
        elif token.endswith("ing") and len(token) > 6:
            token = token[:-3]
        elif token.endswith("ed") and len(token) > 5:
            token = token[:-2]
        elif token.endswith("s") and len(token) > 4 and not token.endswith("ss"):
            token = token[:-1]
        normalized.add(token)
    tokens = normalized
    if "networth" in tokens:
        tokens.update({"net", "worth"})
    if tokens & {"billionaire", "billionaires", "wealth", "wealthy"}:
        tokens.update({"net", "worth"})
    if "convertion" in tokens:
        tokens.discard("convertion")
        tokens.add("conversion")
    if {"dollar", "pkr"}.issubset(tokens):
        tokens.discard("dollar")
        tokens.add("usd")
        if "conversion" in tokens:
            tokens.discard("conversion")
            tokens.add("convert")
    return tokens - STOP_WORDS


def _search_intent_text(query: str) -> str:
    current_match = re.search(
        r"(?:^|\n)Current question:\s*(.*)$",
        query,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not current_match:
        return query.strip()

    current_question = current_match.group(1).strip()
    previous_match = re.search(
        r"(?:^|\n)Previous user question:\s*(.*?)(?=\nCurrent question:)",
        query,
        flags=re.IGNORECASE | re.DOTALL,
    )
    has_reference = re.search(
        r"\b(?:what|how|why|where|when|who|which)\s+(?:is|are|was|were|does|do|did|can|could|would|will|should)\s+(?:it|this|that|these|those|they|he|she)\b"
        r"|\b(?:is|are|was|were|does|do|did|can|could|would|will|should)\s+(?:it|this|that|these|those|they|he|she)\b"
        r"|\b(?:what|how|why|where|when|who|which)\s+about\s+(?:it|this|that|these|those|they|he|she)\b"
        r"|\b(?:its|their|his|her)\b",
        current_question,
        flags=re.IGNORECASE,
    )
    if previous_match and has_reference:
        return f"{previous_match.group(1).strip()} {current_question}"
    return current_question


def _search_query(query: str) -> str:
    original = normalize_common_query_typos(query)
    compact = re.sub(r"[^a-z0-9]", "", original.casefold())
    if re.fullmatch(r"top gaining stocks today", re.sub(r"\s+", " ", original.casefold())):
        return "top gaining stocks today"
    if compact in {"elonnetworth", "elonmusknetworth"}:
        return "Elon Musk net worth"
    if re.search(r"\belon\s+net\s*worth\b", original, re.IGNORECASE):
        return "Elon Musk net worth"
    if re.search(r"\bmost\s+profitt?ed\s+stocks?\b|\bmost\s+profitable\s+stocks?\b", original, re.IGNORECASE):
        if re.search(r"\b(?:today|day|current|now)\b", original, re.IGNORECASE):
            return "top gaining stocks today"

    currency_query = bool(
        re.search(r"\b(?:exchange\s+rate|convert(?:ion)?|currency)\b", original, re.IGNORECASE)
    )
    currency_matches = []
    for code, aliases in CURRENCY_ALIASES.items():
        search_aliases = aliases
        if (
            code == "USD"
            and currency_query
            and re.search(r"\bPKR\b", original, re.IGNORECASE)
        ):
            search_aliases = (*aliases, "US")
        positions = [
            match.start()
            for alias in search_aliases
            for match in re.finditer(
                rf"(?<![a-z]){re.escape(alias)}(?![a-z])",
                original,
                re.IGNORECASE,
            )
        ]
        if positions:
            currency_matches.append((min(positions), code))
    if currency_query:
        found_codes = [
            code for _, code in sorted(currency_matches)
        ]
        if len(found_codes) >= 2:
            base, quote = found_codes[:2]
            return f"{base} to {quote} exchange rate today"
    historical_presidents = re.search(
        r"\b(?P<subject>[a-z][a-z .'-]*?)\s+presidents?\s+"
        r"(?:names?\s+)?from\s+(?P<start>(?:19|20)\d{2})\s+"
        r"to\s+(?P<end>(?:19|20)\d{2})\b",
        original,
        re.IGNORECASE,
    )
    if historical_presidents:
        subject = re.sub(
            r"\b(?:all|list|name|the|who|were|are)\b",
            " ",
            historical_presidents.group("subject"),
            flags=re.IGNORECASE,
        )
        subject = re.sub(r"\s+", " ", subject).strip()
        if subject:
            return (
                f"{subject.title()} presidents from "
                f"{historical_presidents.group('start')} to "
                f"{historical_presidents.group('end')}"
            )
    regional_query = re.fullmatch(
        r"current\s+presidents\s+of\s+countries\s+in\s+(Africa|Asia|Europe|Americas|Oceania)",
        original,
        re.IGNORECASE,
    )
    if regional_query:
        return f"current presidents of countries in {regional_query.group(1).title()}"

    without_possessives = re.sub(r"\b([A-Za-z0-9]+)['’]s\b", r"\1", query, flags=re.IGNORECASE)
    source_terms = re.findall(r"[A-Za-z0-9]+", without_possessives)
    raw_terms = [term.lower() for term in source_terms]
    if {"usd", "pkr"}.issubset(raw_terms):
        return "USD to PKR"
    if {"dollar", "pkr"}.issubset(raw_terms):
        return "USD to PKR"
    if (
        "elon" in raw_terms
        and "musk" not in raw_terms
        and ("networth" in raw_terms or {"net", "worth"}.issubset(raw_terms))
    ):
        return "Elon Musk net worth"
    if {"requests", "timeout"}.issubset(raw_terms):
        detail_terms = [
            term for term in source_terms
            if term.lower() not in STOP_WORDS | {"python", "requests", "timeout"}
        ]
        detail = " ".join(detail_terms) or "parameter"
        return f"Requests library timeout {detail}"

    def normalized_terms(terms_to_normalize: list[str]) -> list[str]:
        terms = []
        for source_term in terms_to_normalize:
            token = source_term.lower()
            if token == "networth":
                terms.extend(("net", "worth"))
            elif token == "convertion":
                terms.append("conversion")
            elif token not in STOP_WORDS:
                terms.append(
                    source_term
                    if source_term.istitle() or source_term.isupper()
                    else token
                )
        return terms

    terms = normalized_terms(source_terms)
    if "of" in raw_terms:
        preposition_index = raw_terms.index("of")
        leading_terms = normalized_terms(source_terms[:preposition_index])
        trailing_terms = normalized_terms(source_terms[preposition_index + 1:])
        if leading_terms and trailing_terms:
            terms = trailing_terms + leading_terms
    return " ".join(terms) or query


def _relevant(query: str, result: dict[str, str]) -> bool:
    query_tokens = _tokens(query)
    if not query_tokens:
        return True
    content = _tokens(_result_text(result))
    matches = query_tokens & content
    named_entities = _requested_entities(query)
    entity_tokens = {
        token
        for entity in named_entities
        for token in _tokens(entity)
    }
    topic_tokens = query_tokens - entity_tokens - {
        token for token in query_tokens if token.isdigit()
    }
    required_matches = min(len(query_tokens), max(1, math.ceil(len(query_tokens) * 0.45)))
    if len(named_entities) > 1:
        required_matches = min(
            required_matches,
            max(1, len(query_tokens) - len(named_entities) + 1),
        )
    if len(matches) < required_matches:
        return False
    if entity_tokens and not (entity_tokens & content):
        return False
    required_concepts = []
    if "president" in query_tokens or {"head", "state"}.issubset(query_tokens):
        required_concepts.append({"president", "leader", "head"})
    if "stock" in query_tokens and query_tokens & {"gain", "profit"}:
        required_concepts.append({"stock"})
        required_concepts.append({"gain", "profit"})
    if query_tokens & {"exchange", "rate"}:
        required_concepts.append({"exchange", "rate"})
    if query_tokens & {"net", "worth"}:
        required_concepts.append({"net", "worth"})
    if any(not (concept & content) for concept in required_concepts):
        return False
    return not topic_tokens or bool(topic_tokens & content)


def _valid_result(result: dict[str, str]) -> bool:
    parsed = urlparse(result.get("url", ""))
    try:
        parsed.port
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(parsed.netloc and result.get("title") and result.get("content"))


def _result_text(result: dict[str, object]) -> str:
    structured = result.get("structured_data")
    structured_text = ""
    if isinstance(structured, dict):
        structured_text = " ".join(
            f"{key} {value}" for key, value in structured.items()
        )
    return " ".join(
        str(value)
        for value in (
            result.get("title", ""),
            result.get("content", ""),
            result.get("published", ""),
            structured_text,
        )
        if value is not None
    )


def _normalize_currency_data(
    item: dict[str, object],
    query: str,
) -> dict[str, object] | None:
    raw = item.get("structured_data")
    data = raw.copy() if isinstance(raw, dict) else {}
    nested = item.get("data")
    if isinstance(nested, dict):
        data = {**nested, **data}
    nested_result = item.get("result")
    if isinstance(nested_result, dict):
        data = {**nested_result, **data}
    pair = _currency_pair(query)
    rates = data.get("conversion_rates") or data.get("rates")
    if pair and isinstance(rates, dict):
        rate_keys = {str(key).upper(): value for key, value in rates.items()}
        base_code = str(
            data.get("base")
            or data.get("base_code")
            or data.get("base_currency")
            or ""
        ).upper()
        if base_code == pair[0] and pair[1] in rate_keys:
            data.update({"base": pair[0], "quote": pair[1], "rate": rate_keys[pair[1]]})
        elif base_code == pair[1] and pair[0] in rate_keys:
            inverse_rate = rate_keys[pair[0]]
            try:
                reciprocal = 1 / float(inverse_rate)
            except (TypeError, ValueError, ZeroDivisionError):
                reciprocal = None
            if reciprocal is not None:
                data.update({"base": pair[0], "quote": pair[1], "rate": reciprocal})
    aliases = {
        "base": ("base", "base_code", "from", "from_currency", "source_currency"),
        "quote": ("quote", "quote_code", "target_code", "to", "to_currency", "target_currency"),
        "rate": ("rate", "conversion_rate", "exchange_rate", "value"),
        "amount": ("amount", "base_amount", "quantity"),
        "timestamp": (
            "timestamp",
            "updated_at",
            "last_update",
            "time_last_update_utc",
            "date",
        ),
    }
    for normalized_key, keys in aliases.items():
        if normalized_key in data and data[normalized_key] is not None:
            continue
        value = next(
            (
                source.get(key)
                for source in (data, item)
                for key in keys
                if source.get(key) is not None
            ),
            None,
        )
        if value is not None:
            data[normalized_key] = value
    if not all(data.get(key) is not None for key in ("base", "quote", "rate")):
        return None
    return {
        **data,
        "base": str(data["base"]).upper(),
        "quote": str(data["quote"]).upper(),
        "rate": data["rate"],
        "amount": data.get("amount", 1),
        **({"timestamp": str(data["timestamp"])} if data.get("timestamp") else {}),
    }


def _normalize_search_result(
    item: dict[str, object],
    provider: str,
    query: str,
) -> dict[str, object]:
    title = _clean(str(item.get("title") or item.get("name") or ""))
    url = _clean(str(item.get("url") or item.get("source_url") or ""))
    content = _clean(str(
        item.get("content")
        or item.get("description")
        or item.get("snippet")
        or item.get("excerpt")
        or ""
    ))
    published = _clean(str(
        item.get("published")
        or item.get("published_date")
        or item.get("timestamp")
        or ""
    ))
    structured = _normalize_currency_data(item, query)
    if structured:
        rate_text = (
            f"{structured['amount']} {structured['base']} = "
            f"{structured['rate']} {structured['quote']}"
        )
        if structured.get("timestamp"):
            rate_text += f" (updated {structured['timestamp']})"
        content = f"{content} {rate_text}".strip()
        published = published or str(structured.get("timestamp") or "")
        title = title or f"{structured['base']} to {structured['quote']} exchange rate"

    normalized: dict[str, object] = {
        "title": title,
        "url": url,
        "content": content,
        "published": published,
        "provider": str(item.get("provider") or provider),
        "score": item.get("score"),
    }
    if structured:
        normalized["structured_data"] = structured
    return normalized


def _result_score(query: str, result: dict[str, object]) -> float:
    supplied = result.get("score")
    if isinstance(supplied, (float, int)):
        return float(supplied)
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    return round(len(query_tokens & _tokens(_result_text(result))) / len(query_tokens), 3)


def _is_authoritative_result(result: dict[str, object]) -> bool:
    hostname = (urlparse(str(result.get("url", ""))).hostname or "").lower()
    return (
        hostname.endswith(".gov")
        or hostname.endswith(".gov.pk")
        or hostname.endswith(".gov.uk")
        or hostname.endswith(".gov.au")
        or hostname.endswith(".govt.nz")
        or hostname.endswith(".gc.ca")
    )


def _has_historical_list_coverage(
    query: str,
    results: list[dict[str, object]],
) -> bool:
    years = re.findall(r"\b(?:19|20)\d{2}\b", query)
    if len(years) < 2:
        return False
    start_year, end_year = int(years[0]), int(years[-1])
    for result in results:
        if not _is_authoritative_result(result):
            continue
        text = " ".join(
            str(result.get(key, ""))
            for key in ("title", "content")
        )
        mentioned_years = {
            int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", text)
        }
        if (
            not mentioned_years
            or min(mentioned_years) > start_year + 1
            or max(mentioned_years) < end_year
        ):
            continue
        office = re.search(r"\bpresident\b", text, re.IGNORECASE)
        named_people = re.findall(
            r"\bPresident\s+(?:Mr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
            text,
        )
        if office and len(set(name.casefold() for name in named_people)) >= 2:
            return True
    return False


def _currency_pair(query: str) -> tuple[str, str] | None:
    codes = re.findall(r"\b[A-Z]{3}\b", query.upper())
    known_codes = {code for code in CURRENCY_ALIASES}
    selected = [code for code in codes if code in known_codes]
    return (selected[0], selected[1]) if len(selected) >= 2 else None


def _has_structured_currency_evidence(
    query: str,
    results: list[dict[str, object]],
) -> bool:
    pair = _currency_pair(query)
    if pair is None:
        return False
    for result in results:
        structured = result.get("structured_data")
        if not isinstance(structured, dict):
            continue
        if (
            str(structured.get("base", "")).upper() == pair[0]
            and str(structured.get("quote", "")).upper() == pair[1]
            and isinstance(structured.get("rate"), (float, int, str))
            and bool(re.search(r"\d", str(structured.get("rate"))))
        ):
            return True
    return False


def _has_textual_currency_rate(
    query: str,
    results: list[dict[str, object]],
) -> bool:
    pair = _currency_pair(query)
    if pair is None:
        return False
    for result in results:
        text = _result_text(result)
        has_pair = all(
            re.search(rf"(?<!\w){code}(?!\w)", text, re.IGNORECASE)
            for code in pair
        )
        has_numeric_rate = bool(
            re.search(r"(?:=\s*|rate\s*(?:is|:)?\s*)\d+(?:[.,]\d+)?", text, re.IGNORECASE)
        )
        if has_pair and has_numeric_rate:
            return True
    return False


def _rank_results(
    results: list[dict[str, str]],
    limit: int,
    query: str | None = None,
) -> list[dict[str, str]]:
    def authority(result: dict[str, str]) -> int:
        hostname = (urlparse(result["url"]).hostname or "").lower().removeprefix("www.")
        if hostname.endswith(".gov"):
            return 6
        return max(
            (
                score
                for domain, score in AUTHORITATIVE_DOMAINS.items()
                if hostname == domain or hostname.endswith(f".{domain}")
            ),
            default=0,
        )

    def relevance(result: dict[str, str]) -> int:
        if query is None:
            return 0
        return len(_tokens(" ".join((result.get("title", ""), result.get("content", "")))) & _tokens(query))

    return sorted(results, key=lambda result: (authority(result), relevance(result)), reverse=True)[:limit]


def _relevant_page_text(markdown: str, query: str, limit: int = 4) -> str:
    query_tokens = _tokens(query)
    paragraphs = []
    for index, paragraph in enumerate(re.split(r"\n\s*\n", markdown)):
        cleaned = _clean(paragraph)
        if len(cleaned) < 35:
            continue
        if re.match(r"(?i)^(?:title|url source|markdown content)\s*:", cleaned):
            continue
        overlap = query_tokens & _tokens(cleaned)
        if overlap:
            paragraphs.append((overlap, index, cleaned))
    selected = []
    covered_tokens = set()
    remaining = paragraphs.copy()
    while remaining and len(selected) < limit:
        remaining.sort(
            key=lambda item: (
                -len(item[0] - covered_tokens),
                -len(item[0]),
                item[1],
            )
        )
        paragraph = remaining.pop(0)
        if not (paragraph[0] - covered_tokens):
            break
        selected.append(paragraph)
        covered_tokens.update(paragraph[0])
    return "\n\n".join(item[2][:600] for item in selected)[:1800]


def _fetch_source_text(result: dict[str, str], query: str) -> str:
    response = _search_request(
        requests.get,
        f"https://r.jina.ai/{result['url']}",
        headers={"User-Agent": "CombatAircraftAI/1.0", "Accept": "text/plain"},
        timeout=20,
    )
    return _relevant_page_text(response.text, query)


def _enrich_search_results(
    results: list[dict[str, str]],
    query: str,
    max_pages: int = 3,
) -> list[dict[str, str]]:
    eligible = []
    for index, result in enumerate(results):
        hostname = (urlparse(result["url"]).hostname or "").lower().removeprefix("www.")
        if hostname.endswith(".gov") or any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain, score in AUTHORITATIVE_DOMAINS.items()
            if score >= 4
        ):
            eligible.append((index, result))

    selected = eligible[:max_pages]
    if not selected:
        return results
    with ThreadPoolExecutor(max_workers=len(selected)) as executor:
        futures = {
            index: executor.submit(_fetch_source_text, result, query)
            for index, result in selected
        }
        enriched_results = [result.copy() for result in results]
        for index, result in selected:
            try:
                content = futures[index].result()
            except requests.RequestException as error:
                hostname = urlparse(result["url"]).hostname
                LOGGER.warning("Could not retrieve full text from %s: %s", hostname, error)
                continue
            if content:
                enriched_results[index]["content"] = content
            else:
                LOGGER.info(
                    "Full-text retrieval from %s contained no query-relevant passages; using its search snippet.",
                    urlparse(result["url"]).hostname,
                )
    return enriched_results


def _decode_bing_url(url: str) -> str:
    parsed = urlparse(url)
    encoded_target = parse_qs(parsed.query).get("u", [""])[0]
    if encoded_target.startswith("a1"):
        try:
            encoded_value = encoded_target[2:]
            padding = "=" * (-len(encoded_value) % 4)
            decoded = base64.urlsafe_b64decode(encoded_value + padding).decode("utf-8")
            if urlparse(decoded).scheme in {"http", "https"}:
                return decoded
        except (ValueError, UnicodeDecodeError):
            pass
    return url


def _extract_bing_published(snippet: str) -> str:
    cleaned = (snippet or "").strip()
    if not cleaned:
        return ""
    published_match = re.search(r"(?is)^Published\s*:\s*(.+?)(?:\n|$)", cleaned)
    if published_match:
        return _clean(published_match.group(1))
    for separator in ["�", "\u2014", "\u2013", "•", "\n\n", "\n"]:
        if separator in cleaned:
            prefix, _ = cleaned.split(separator, 1)
            prefix = prefix.strip()
            if re.search(r"(?i)(ago|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)|\d{1,2},\s*\d{4}|\d{4}-\d{2}-\d{2})", prefix):
                return _clean(prefix)
            break
    return ""


def _bing_content(snippet: str) -> str:
    cleaned = (snippet or "").strip()
    if not cleaned:
        return ""
    published = _extract_bing_published(cleaned)
    if published:
        if re.search(r"(?is)^Published\s*:\s*" + re.escape(published), cleaned):
            cleaned = re.sub(r"(?is)^Published\s*:\s*" + re.escape(published) + r"\s*", "", cleaned).strip()
        for separator in ["�", "\u2014", "\u2013", "•", "\n\n", "\n"]:
            if separator in cleaned:
                _, suffix = cleaned.split(separator, 1)
                cleaned = suffix.strip()
                break
    return _clean(cleaned)


def _parse_bing_results(markdown: str, query: str, limit: int) -> list[dict[str, str]]:
    headings = list(
        re.finditer(
            r"(?m)^\s*(?:\d+\.\s*)?##\s+\[(?P<title>.+?)\]"
            r"\((?P<url>https?://[^)\s]+)\)\s*$",
            markdown,
        )
    )
    by_url = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        snippet = markdown[heading.end():end]
        published = _extract_bing_published(snippet)
        result = {
            "title": _clean(re.sub(r"\*+", "", heading.group("title"))),
            "url": _decode_bing_url(heading.group("url")),
            "content": _bing_content(snippet),
            "published": published,
        }
        if _valid_result(result) and _relevant(query, result):
            existing = by_url.get(result["url"])
            if existing is None or len(result["content"]) > len(existing["content"]):
                by_url[result["url"]] = result
    return list(by_url.values())[:limit]


def _search_request(method, url: str, max_attempts: int = SEARCH_MAX_ATTEMPTS, **kwargs):
    for attempt in range(max_attempts):
        try:
            response = method(url, **kwargs)
        except requests.RequestException:
            if attempt + 1 == max_attempts:
                raise
            LOGGER.warning("Web search request failed; retrying once.")
            time.sleep(0.5 * (2 ** attempt))
            continue

        status = getattr(response, "status_code", None)
        retryable = isinstance(status, int) and (status == 429 or 500 <= status < 600)
        if retryable and attempt + 1 < max_attempts:
            retry_after = 0.5 * (2 ** attempt)
            try:
                retry_after = min(
                    max(float(response.headers.get("Retry-After", retry_after)), 0),
                    5,
                )
            except (TypeError, ValueError):
                pass
            LOGGER.warning("Web search provider returned HTTP %s; retrying once.", status)
            time.sleep(retry_after)
            continue
        response.raise_for_status()
        return response

    raise RuntimeError("Web search request ended without a response.")


def _bing_search(
    query: str,
    limit: int,
    relevance_query: str | None = None,
) -> list[dict[str, str]]:
    response = _search_request(
        requests.get,
        BING_READER_URL,
        params={"q": _search_query(query), "setlang": "en-US"},
        headers={"User-Agent": "CombatAircraftAI/1.0", "Accept": "text/plain"},
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    markdown = response.text
    if "AuthenticationRequiredError" in markdown or "CAPTCHA" in markdown:
        raise ValueError("Live web search is temporarily blocked by the search provider.")
    results = _rank_results(
        _parse_bing_results(markdown, relevance_query or query, limit * 2),
        limit,
        relevance_query or query,
    )
    LOGGER.info("Web search provider=Bing HTTP %s parsed_results=%s", response.status_code, len(results))
    return _rank_results(results, limit, relevance_query or query)


def _tavily_search(
    query: str,
    limit: int,
    api_key: str,
    relevance_query: str | None = None,
) -> list[dict[str, str]]:
    response = _search_request(
        requests.post,
        TAVILY_SEARCH_URL,
        json={
            "api_key": api_key,
            "query": query,
            "topic": "general",
            "search_depth": "advanced",
            "include_answer": False,
            "max_results": limit,
        },
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("Tavily returned an invalid search response.")
    results = []
    for item in payload["results"]:
        if not isinstance(item, dict):
            continue
        result = {
            "title": _clean(item.get("title")),
            "url": _clean(item.get("url")),
            "content": _clean(item.get("content")),
            "published": _clean(item.get("published_date")),
        }
        if _valid_result(result) and _relevant(relevance_query or query, result):
            results.append(result)
    return results


def _brave_search(
    query: str,
    limit: int,
    api_key: str,
    relevance_query: str | None = None,
) -> list[dict[str, str]]:
    response = _search_request(
        requests.get,
        BRAVE_SEARCH_URL,
        max_attempts=1,
        params={"q": query, "count": min(max(limit, 1), 20), "safesearch": "moderate"},
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    payload = response.json()
    web_payload = payload.get("web") if isinstance(payload, dict) else None
    items = web_payload.get("results") if isinstance(web_payload, dict) else None
    if not isinstance(items, list):
        raise ValueError("Brave returned an invalid search response.")
    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result = {
            "title": _clean(item.get("title")),
            "url": _clean(item.get("url")),
            "content": _clean(item.get("description")),
            "published": _clean(item.get("page_age")),
        }
        if _valid_result(result) and _relevant(relevance_query or query, result):
            results.append(result)
    return results[:limit]


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, limit: int, relevance_query: str) -> list[dict[str, str]]: ...


class BingProvider:
    name = "Bing"

    def search(self, query: str, limit: int, relevance_query: str) -> list[dict[str, str]]:
        return _bing_search(query, limit, relevance_query=relevance_query)


class TavilyProvider:
    name = "Tavily"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, limit: int, relevance_query: str) -> list[dict[str, str]]:
        return _tavily_search(query, limit, self.api_key, relevance_query=relevance_query)


class BraveProvider:
    name = "Brave"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, limit: int, relevance_query: str) -> list[dict[str, str]]:
        return _brave_search(query, limit, self.api_key, relevance_query=relevance_query)


def _result_sufficient(
    query: str,
    results: list[dict[str, str]],
    intent: str | None = None,
    provider: str = "unknown",
) -> bool:
    intent = intent or classify_question(query)
    for index, result in enumerate(results, start=1):
        LOGGER.info(
            "[EVIDENCE_GATE] provider=%s intent=%s result_count=%s index=%s "
            "title=%r url=%r snippet=%r score=%s",
            result.get("provider", provider),
            intent,
            len(results),
            index,
            str(result.get("title", ""))[:240],
            str(result.get("url", ""))[:500],
            str(result.get("content", ""))[:600],
            _result_score(query, result),
        )
    useful = [
        result for result in results
        if _valid_result(result) and _relevant(query, result)
        and (
            len(str(result.get("content", "")).strip()) >= 30
            or _has_structured_currency_evidence(query, [result])
        )
    ]
    unique_urls = {_canonical_url(result) for result in useful}
    required = 2 if intent in {LIST, MULTI_PART} else 3 if intent == RESEARCH_WEB else 1
    if intent == LIST:
        requested = re.search(r"\b(?:list|name)\s+(\d{1,2})\b", query, re.IGNORECASE)
        if requested:
            required = min(max(int(requested.group(1)), 3), 6)
    enough_sources = len(unique_urls) >= required
    if (
        not enough_sources
        and intent == LIST
        and _has_historical_list_coverage(query, useful)
    ):
        enough_sources = True
        LOGGER.info(
            "[EVIDENCE_GATE] accepted_single_authoritative_source=true "
            "reason=complete_historical_coverage"
        )
    entities = _requested_entities(query)
    combined_evidence = " ".join(_result_text(result) for result in useful)
    entity_coverage = all(
        re.search(rf"(?<!\w){re.escape(entity)}(?!\w)", combined_evidence, re.IGNORECASE)
        for entity in entities
    )
    sufficient = enough_sources and entity_coverage
    LOGGER.info(
        "[EVIDENCE_GATE] provider=%s intent=%s sufficient=%s sources=%s required=%s "
        "entity_coverage=%s",
        provider,
        intent,
        sufficient,
        len(unique_urls),
        required,
        entity_coverage,
    )
    return sufficient


def _requested_entities(query: str) -> list[str]:
    intent_query = _search_intent_text(query)
    ignored = {
        "a", "about", "also", "an", "and", "additionally", "compare", "current",
        "describe", "enumerate", "explain", "find", "for", "give", "how", "in",
        "latest", "list", "name", "of", "on", "research", "show", "summarize",
        "summarise", "tell", "the", "to", "what", "when", "where", "which", "who",
        "why",
    }
    entities = []
    for match in re.finditer(
        r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,}))*\b",
        intent_query,
    ):
        words = match.group(0).split()
        while words and words[0].casefold() in ignored:
            words.pop(0)
        candidate = " ".join(words)
        if not candidate:
            continue
        if candidate.casefold() not in {entity.casefold() for entity in entities}:
            entities.append(candidate)
    return entities


def _canonical_url(result: dict[str, str]) -> str:
    parsed = urlparse(result.get("url", ""))
    hostname = (parsed.hostname or "").lower().removeprefix("www.")
    port = parsed.port
    netloc = f"{hostname}:{port}" if port and port != 443 else hostname
    query = urlencode(sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in {"fbclid", "gclid", "ref", "source"}
    ))
    return urlunparse((
        parsed.scheme.lower(),
        netloc,
        parsed.path.rstrip("/") or "/",
        parsed.params,
        query,
        "",
    ))


def _merge_results(
    primary: list[dict[str, str]],
    fallback: list[dict[str, str]],
    query: str,
    limit: int,
) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for result in primary + fallback:
        if not _valid_result(result) or not _relevant(query, result):
            continue
        key = _canonical_url(result)
        existing = merged.get(key)
        if existing is None:
            merged[key] = result.copy()
            continue
        preferred = (
            result.copy()
            if len(str(result.get("content", ""))) > len(str(existing.get("content", "")))
            else existing.copy()
        )
        structured = result.get("structured_data") or existing.get("structured_data")
        if isinstance(structured, dict):
            preferred["structured_data"] = structured
        preferred["score"] = max(
            _result_score(query, result),
            _result_score(query, existing),
        )
        merged[key] = preferred

    candidates = list(merged.values())
    selected: list[dict[str, str]] = []
    for result in _rank_results(candidates, len(candidates), query):
        hostname = (urlparse(result["url"]).hostname or "").lower().removeprefix("www.")
        tokens = _tokens(result["content"])
        duplicate = False
        for earlier in selected:
            earlier_host = (urlparse(earlier["url"]).hostname or "").lower().removeprefix("www.")
            earlier_tokens = _tokens(earlier["content"])
            union = tokens | earlier_tokens
            if (
                hostname == earlier_host
                and len(tokens) >= 12
                and len(earlier_tokens) >= 12
                and union
                and len(tokens & earlier_tokens) / len(union) >= 0.92
            ):
                duplicate = True
                break
        if not duplicate:
            selected.append(result)
    return selected[:limit]


LARGE_LIST_REGIONS = ("Africa", "Asia", "Europe", "Americas", "Oceania")


def _search_queries(query: str, intent: str) -> list[tuple[str, str]]:
    if intent == LARGE_LIST:
        return [
            (f"current presidents of countries in {region}", region)
            for region in LARGE_LIST_REGIONS
        ]
    if intent == LIST and re.search(
        r"\bpresidents?\b.*\b(?:19|20)\d{2}\b.*\b(?:19|20)\d{2}\b",
        query,
        re.IGNORECASE,
    ):
        subject_before_match = re.search(
            r"\b(?P<subject>[a-z][a-z .'-]*?)\s+presidents?\s+"
            r"(?:names?\s+)?from\s+(?P<start>(?:19|20)\d{2})\s+"
            r"to\s+(?P<end>(?:19|20)\d{2})\b",
            query,
            re.IGNORECASE,
        )
        if subject_before_match:
            subject = re.sub(
                r"\b(?:all|list|name|the|who|were|are)\b",
                " ",
                subject_before_match.group("subject"),
                flags=re.IGNORECASE,
            )
            subject = re.sub(r"\s+", " ", subject).strip()
            if subject:
                start, end = subject_before_match.group("start", "end")
                return [
                    (_search_query(query), ""),
                    (f"{subject.title()} former presidents {start} {end}", ""),
                ]
        historical_match = re.search(
            r"\bpresidents?\s+(?:of\s+)?(?P<subject>.+?)\s+from\s+"
            r"(?P<start>(?:19|20)\d{2})\s+to\s+(?P<end>(?:19|20)\d{2})",
            query,
            re.IGNORECASE,
        )
        if historical_match:
            subject = re.sub(r"\b(?:the|all|who|were|are)\b", " ", historical_match.group("subject"), flags=re.IGNORECASE)
            subject = re.sub(r"\s+", " ", subject).strip()
            second_query = (
                f"list of {subject} presidents "
                f"{historical_match.group('start')} {historical_match.group('end')}"
            )
        else:
            second_query = re.sub(
                r"\bwho\s+were\b|\bfrom\b|\bto\b",
                " ",
                query,
                flags=re.IGNORECASE,
            ).replace("?", " timeline list")
        return [
            (_search_query(query), ""),
            (second_query, ""),
        ]
    return [(_search_query(query), "")]


def _evidence_sufficiency_reason(
    query: str,
    results: list[dict[str, str]],
    intent: str,
) -> str | None:
    if not results:
        return "no usable results"
    if _currency_pair(query):
        if (
            _has_structured_currency_evidence(query, results)
            or _has_textual_currency_rate(query, results)
        ):
            LOGGER.info(
                "[EVIDENCE_GATE] accepted_currency_rate=true structured=%s currency_pair=%s",
                _has_structured_currency_evidence(query, results),
                _currency_pair(query),
            )
            return None
        return "currency result did not contain a verified rate for the requested pair"
    entities = _requested_entities(query)
    combined = " ".join(
        _result_text(result)
        for result in results
    )
    missing_entities = [
        entity for entity in entities
        if not re.search(rf"(?<!\w){re.escape(entity)}(?!\w)", combined, re.IGNORECASE)
    ]
    if missing_entities:
        return f"missing required terms: {', '.join(missing_entities)}"
    providers = sorted({
        str(result.get("provider"))
        for result in results
        if result.get("provider")
    })
    provider = ",".join(providers) or "unknown"
    if not _result_sufficient(query, results, intent, provider=provider):
        if intent == LIST and _has_historical_list_coverage(query, results):
            LOGGER.info(
                "[EVIDENCE_GATE] final_acceptance=complete_historical_official_list"
            )
            return None
        return "too few distinct, relevant evidence sources"
    return None


def _provider_attempt(
    provider: SearchProvider,
    query: str,
    limit: int,
    relevance_query: str,
) -> tuple[list[dict[str, str]], Exception | None, float]:
    started = time.perf_counter()
    try:
        raw_results = provider.search(query, limit, relevance_query)
        results = []
        for raw_result in raw_results:
            normalized = _normalize_search_result(raw_result, provider.name, relevance_query)
            if _valid_result(normalized):
                normalized["score"] = _result_score(relevance_query, normalized)
                results.append(normalized)
    except (requests.RequestException, ValueError, RuntimeError, TypeError, KeyError) as error:
        return [], error, time.perf_counter() - started
    return results, None, time.perf_counter() - started


def _safe_query_for_log(query: str) -> str:
    return f"<redacted:{len(query)} chars>"


def search_online(
    query: str,
    limit: int = 6,
    metrics: dict[str, object] | None = None,
    intent: str | None = None,
) -> list[dict[str, str]]:
    search_started = time.perf_counter()
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    primary: SearchProvider = TavilyProvider(tavily_api_key) if tavily_api_key else BingProvider()
    fallback = BraveProvider(brave_api_key) if brave_api_key else None
    primary_name = primary.name
    original_query = _search_intent_text(query)
    normalized_query = _search_query(original_query)
    cache_intent = intent or classify_question(original_query)
    normalized_intent_query = normalize_common_query_typos(original_query)
    queries = _search_queries(normalized_intent_query, cache_intent)
    if cache_intent == LARGE_LIST:
        normalized_query = " | ".join(provider_query for provider_query, _ in queries)
    cache_key = (
        f"{primary_name}+Brave:{bool(fallback)}+intent:{cache_intent}",
        normalized_query.casefold(),
        limit,
    )
    now = time.monotonic()
    with _search_cache_lock:
        cached = _search_cache.get(cache_key)
        if cached and now - cached[0] < SEARCH_CACHE_TTL_SECONDS:
            cached_results, cached_metrics = cached[1], cached[2]
            LOGGER.info(
                "[SEARCH] intent=%s original=%r normalized=%r cache_hit=true",
                cache_intent,
                _safe_query_for_log(original_query),
                _safe_query_for_log(normalized_query),
            )
            if metrics is not None:
                metrics.update(cached_metrics)
                metrics.update({
                    "intent": cache_intent,
                    "original_query": original_query,
                    "normalized_query": normalized_query,
                    "fallback_provider": fallback.name if fallback else "Brave",
                    "fallback_configured": fallback is not None,
                    "cache_hit": True,
                    "search_total_ms": round((time.perf_counter() - search_started) * 1000, 2),
                })
            return [result.copy() for result in cached_results]
        for key in [
            key for key, (cached_at, _, _) in _search_cache.items()
            if now - cached_at >= SEARCH_CACHE_TTL_SECONDS
        ]:
            del _search_cache[key]

    primary_results: list[dict[str, str]] = []
    fallback_results: list[dict[str, str]] = []
    primary_errors = []
    fallback_errors = []
    primary_time = 0.0
    fallback_time = 0.0
    region_results: dict[str, list[dict[str, str]]] = {}
    for provider_query, region in queries:
        relevance_query = provider_query
        normalized_provider_query = _search_query(provider_query)
        found, error, elapsed = _provider_attempt(
            primary,
            normalized_provider_query,
            min(limit, 6) if region else limit,
            relevance_query,
        )
        primary_time += elapsed
        if error:
            primary_errors.append(type(error).__name__)
        primary_results.extend(found)
        if region:
            region_results[region] = found
        primary_sufficient = _result_sufficient(
            relevance_query,
            found,
            LIST if region else cache_intent,
            provider=primary.name,
        )
        if fallback and not primary_sufficient:
            fallback_found, fallback_error, fallback_elapsed = _provider_attempt(
                fallback,
                normalized_provider_query,
                min(limit, 6) if region else limit,
                relevance_query,
            )
            fallback_time += fallback_elapsed
            if fallback_error:
                fallback_errors.append(type(fallback_error).__name__)
                LOGGER.warning(
                    "[FALLBACK] provider=%s status=error error_type=%s",
                    fallback.name,
                    type(fallback_error).__name__,
                )
            fallback_results.extend(fallback_found)
            _result_sufficient(
                relevance_query,
                fallback_found,
                LIST if region else cache_intent,
                provider=fallback.name,
            )
            if region:
                region_results[region].extend(fallback_found)

    merge_started = time.perf_counter()
    if cache_intent == LARGE_LIST:
        results = _merge_results(primary_results, fallback_results, "presidents", limit)
    elif fallback_results:
        results = _merge_results(primary_results, fallback_results, normalized_query, limit)
    else:
        results = _merge_results(primary_results, [], normalized_query, limit)
    merge_time = time.perf_counter() - merge_started

    covered_regions = [
        region
        for region, evidence in region_results.items()
        if any(
            region.casefold() in (result.get("title", "") + " " + result.get("content", "")).casefold()
            for result in evidence
        )
    ]
    missing_regions = [region for region in LARGE_LIST_REGIONS if region not in covered_regions]
    if cache_intent != LARGE_LIST:
        covered_regions = []
        missing_regions = []

    insufficiency_reason = _evidence_sufficiency_reason(
        normalized_query,
        results,
        cache_intent,
    )
    evidence_sufficient = insufficiency_reason is None
    if cache_intent in {CURRENT_WEB, LIVE_MARKET} and not evidence_sufficient:
        results = []

    primary_status = "success" if primary_results else "error" if primary_errors else "empty"
    fallback_status = (
        "not_configured" if fallback is None
        else "success" if fallback_results
        else "error" if fallback_errors
        else "empty"
    )
    LOGGER.info(
        "[SEARCH] intent=%s original=%r normalized=%r",
        cache_intent,
        _safe_query_for_log(original_query),
        _safe_query_for_log(normalized_query),
    )
    LOGGER.info(
        "[PRIMARY] provider=%s status=%s results=%s time=%.2fs",
        primary_name, primary_status, len(primary_results), primary_time,
    )
    LOGGER.info(
        "[FALLBACK] provider=%s status=%s results=%s time=%.2fs",
        fallback.name if fallback else "Brave",
        fallback_status, len(fallback_results), fallback_time,
    )
    LOGGER.info(
        "[MERGE] results_before=%s duplicates_removed=%s final_results=%s sufficient=%s",
        len(primary_results) + len(fallback_results),
        max(len(primary_results) + len(fallback_results) - len(results), 0),
        len(results),
        evidence_sufficient,
    )
    if metrics is not None:
        metrics.update({
            "intent": cache_intent,
            "original_query": original_query,
            "normalized_query": normalized_query,
            "primary_provider": primary_name,
            "primary_status": primary_status,
            "primary_result_count": len(primary_results),
            "primary_error": primary_errors[-1] if primary_errors else None,
            "primary_search_ms": round(primary_time * 1000, 2),
            "fallback_provider": fallback.name if fallback else "Brave",
            "fallback_configured": fallback is not None,
            "fallback_status": fallback_status,
            "fallback_result_count": len(fallback_results),
            "fallback_error": fallback_errors[-1] if fallback_errors else None,
            "fallback_search_ms": round(fallback_time * 1000, 2),
            "merge_dedup_ms": round(merge_time * 1000, 2),
            "final_result_count": len(results),
            "result_count": len(results),
            "evidence_sufficient": evidence_sufficient,
            "insufficiency_reason": insufficiency_reason,
            "region_coverage": covered_regions,
            "missing_regions": missing_regions,
            "cache_hit": False,
        })

    if not results:
        if metrics is not None:
            metrics["search_total_ms"] = round((time.perf_counter() - search_started) * 1000, 2)
        LOGGER.warning("[SEARCH] intent=%s status=insufficient_evidence", cache_intent)
        return []

    enrichment_started = time.perf_counter()
    results = _enrich_search_results(
        results,
        normalized_query,
        max_pages=1 if cache_intent in {LIVE_MARKET, CURRENT_WEB} else 3,
    )
    if metrics is not None:
        metrics["enrichment_ms"] = round((time.perf_counter() - enrichment_started) * 1000, 2)
    with _search_cache_lock:
        if len(_search_cache) >= SEARCH_CACHE_MAX_ENTRIES:
            oldest_key = min(_search_cache, key=lambda key: _search_cache[key][0])
            del _search_cache[oldest_key]
        cache_metrics = dict(metrics or {})
        _search_cache[cache_key] = (
            time.monotonic(),
            [result.copy() for result in results],
            cache_metrics,
        )
    if metrics is not None:
        metrics["result_count"] = len(results)
        metrics["final_result_count"] = len(results)
        metrics["search_total_ms"] = round((time.perf_counter() - search_started) * 1000, 2)
    LOGGER.info(
        "[SEARCH] status=success final_results=%s time=%.2fs",
        len(results),
        time.perf_counter() - search_started,
    )
    return results
