import re

SINGLE_FACT = "single_fact"
LIST = "list"
MULTI_PART = "multi_part"
RESEARCH_WEB = "research/web"
CURRENT_WEB = "current_web"
LIVE_MARKET = "live_market"
LARGE_LIST = "large_list"

_LIST_PATTERNS = (
    r"\b(?:list|enumerate|name)\b",
    r"\bwho\s+(?:were|are)\b",
    r"\bwhat\s+are\s+the\s+(?:different|various|types|names|currencies|presidents)\b",
    r"\b(?:all|each|every)\b",
    r"\b(?:currencies|presidents|types|kinds|examples|aircraft|items|names)\s+of\b",
)
_LARGE_LIST_PATTERNS = (
    r"\b(?:all|every)\s+(?:of\s+the\s+)?presidents?\s+(?:of\s+)?(?:all\s+)?countries\b",
    r"\b(?:presidents|leaders|heads\s+of\s+state)\s+of\s+(?:all\s+)?countries\b",
    r"\b(?:all|every)\s+countries\b",
)
_LIVE_MARKET_PATTERNS = (
    r"\bstocks?\b.*\b(?:today|day|current|now|gainers?|profitable|profitted|profit)\b",
    r"\b(?:today|day|current|now)\b.*\bstocks?\b",
    r"\b(?:top|most)\s+(?:profitable|profitted|gaining)\s+stocks?\b",
)
_CURRENT_PATTERNS = (
    r"\b(?:current|currently|today|now|latest|live|up[\s-]to[\s-]date)\b",
    r"\bexchange\s+rate\b",
    r"\b(?:stock|market|share)\s+price\b",
)
_MULTI_PART_PATTERNS = (
    r"\bcompare\b",
    r"\bdifference\s+between\b",
    r"\b(?:and\s+also|additionally)\b",
    r"\bwhat\s+.+\?\s*(?:and|also)\s*(?:what|how|why|when|where|who)\b",
)
_RESEARCH_PATTERNS = (
    r"\bresearch\b",
    r"\bmultiple\s+sources\b",
    r"\b(?:latest|recent)\s+(?:news|developments|research)\b",
)

_COMMON_QUERY_TYPOS = (
    (r"\bnaem\b", "name"),
    (r"\bcurency\b", "currency"),
    (r"\bexhcange\b", "exchange"),
    (r"\bratebetween\b", "rate between"),
)


def normalize_common_query_typos(query: str) -> str:
    normalized = query
    for pattern, replacement in _COMMON_QUERY_TYPOS:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


def classify_question(query: str, *, web: bool = False) -> str:
    query = normalize_common_query_typos(query)
    if any(re.search(pattern, query, flags=re.IGNORECASE) for pattern in _LARGE_LIST_PATTERNS):
        return LARGE_LIST
    if any(re.search(pattern, query, flags=re.IGNORECASE) for pattern in _LIVE_MARKET_PATTERNS):
        return LIVE_MARKET
    if any(re.search(pattern, query, flags=re.IGNORECASE) for pattern in _CURRENT_PATTERNS):
        return CURRENT_WEB
    if any(re.search(pattern, query, flags=re.IGNORECASE) for pattern in _LIST_PATTERNS):
        return LIST
    if ";" in query or len(re.findall(r"\?", query)) > 1 or any(
        re.search(pattern, query, flags=re.IGNORECASE)
        for pattern in _MULTI_PART_PATTERNS
    ):
        return MULTI_PART
    if web or any(
        re.search(pattern, query, flags=re.IGNORECASE)
        for pattern in _RESEARCH_PATTERNS
    ):
        return RESEARCH_WEB
    return SINGLE_FACT


def retrieval_limits(intent: str) -> tuple[int, int]:
    if intent in {SINGLE_FACT, CURRENT_WEB, LIVE_MARKET}:
        return 6, 3
    if intent in {LIST, LARGE_LIST}:
        return 12, 8
    if intent == MULTI_PART:
        return 12, 8
    return 12, 10


def requires_live_web(intent: str) -> bool:
    return intent in {CURRENT_WEB, LIVE_MARKET, LARGE_LIST}


def completeness_instructions(intent: str) -> str:
    if intent in {LIST, LARGE_LIST}:
        return (
            "This is a list question. Use all distinct answer items supported by the "
            "evidence, present them as a readable list, and do not stop at the first "
            "matching item. For worldwide lists, identify which regions the evidence "
            "covers and explicitly note regions/items the retrieved sources leave out. "
            "Include dates or qualifications when the sources provide them."
        )
    if intent == LIVE_MARKET:
        return (
            "This is a live financial-market question. Use only the supplied current "
            "search evidence, identify its date/time or source timestamp when available, "
            "and do not invent a winning stock, price, or return. Name a winning stock "
            "only if a supplied source explicitly identifies it as the top gainer for "
            "the requested date; otherwise say the evidence does not establish a winner."
        )
    if intent == CURRENT_WEB:
        return (
            "This asks for current information. Use the supplied live web evidence, "
            "identify its date/time when available, and do not substitute stale local data."
        )
    if intent == MULTI_PART:
        return (
            "This question has multiple parts. Address each part separately; if the "
            "supplied evidence does not answer a part, explicitly say so rather than "
            "letting another part stand in for it."
        )
    if intent == RESEARCH_WEB:
        return (
            "This is a web research question. Address each requested entity or comparison "
            "aspect, synthesize useful distinct supplied sources, preserve their numbered "
            "citations, and do not rely on only the first result."
        )
    return "Answer directly from the strongest relevant evidence."


def check_answer_completeness(
    query: str,
    intent: str,
    evidence: str,
    answer: str,
) -> dict[str, object]:
    evidence_blocks = sum(
        1 for block in re.split(r"\n\s*\n", evidence.strip()) if block.strip()
    )
    answer_lines = [
        line for line in answer.splitlines()
        if line.strip() and re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", line)
    ]
    citation_count = len(re.findall(r"\[\d+\]", answer))
    answer_items = len(answer_lines) if intent == LIST else max(len(answer_lines), citation_count)
    enough_evidence = evidence_blocks > 1 or len(evidence.strip()) >= 120
    complete = True
    reason = "checked"
    research_needs_multiple = intent == RESEARCH_WEB and bool(
        re.search(r"\b(?:research|multiple\s+sources|compare|comparison)\b", query, re.IGNORECASE)
    )
    if (intent in {LIST, LARGE_LIST} or research_needs_multiple) and enough_evidence and answer_items < 2:
        complete = False
        reason = "multiple evidence blocks were supplied but the answer is not structured as a multi-item response"
    elif intent == MULTI_PART and evidence_blocks < 2:
        complete = False
        reason = "the multi-part query did not receive distinct evidence blocks"
    return {
        "complete": complete,
        "reason": reason,
        "evidence_blocks": evidence_blocks,
        "answer_items": answer_items,
    }
