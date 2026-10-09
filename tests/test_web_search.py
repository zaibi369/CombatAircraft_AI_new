import unittest
import base64
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient

import server
import web_search


class WebSearchTests(unittest.TestCase):
    def test_bing_search_returns_relevant_https_results(self):
        response = unittest.mock.Mock()
        response.text = """Title: Elon Musk net worth - Bing
## [Elon Musk - Forbes](https://www.forbes.com/profile/elon-musk/)

Published: Wed, 30 Sep 2026 10:00:00 GMT
Elon Musk net worth and profile.
"""
        response.raise_for_status.return_value = None
        with patch.object(web_search.requests, "get", return_value=response):
            results = web_search._bing_search("Elon Musk net worth", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Elon Musk - Forbes")
        self.assertEqual(results[0]["published"], "Wed, 30 Sep 2026 10:00:00 GMT")

    def test_bing_search_parses_numbered_markdown_and_split_networth_query(self):
        response = unittest.mock.Mock()
        response.text = """Title: elon networth - Bing
Markdown Content:
About 87,300 results

1. ## [**Elon** University](https://www.elon.edu/)

Experiential learning and outstanding teaching.

2. ## [**Elon Musk** Bio, Net Worth, Tesla](https://example.com/elon-musk)

Elon Musk biography and net worth estimates.
"""
        response.raise_for_status.return_value = None
        with patch.object(web_search.requests, "get", return_value=response) as search_request:
            results = web_search._bing_search("elon networth", limit=5)

        self.assertEqual(
            search_request.call_args.kwargs["params"]["q"],
            "Elon Musk net worth",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Elon Musk Bio, Net Worth, Tesla")
        self.assertEqual(results[0]["url"], "https://example.com/elon-musk")
        self.assertIn("net worth estimates", results[0]["content"])

    def test_search_query_removes_question_filler_and_puts_subject_first(self):
        self.assertEqual(
            web_search._search_query(
                "What is the latest reported net worth of Elon Musk?"
            ),
            "Elon Musk net worth",
        )

    def test_search_query_refines_known_python_requests_timeout_topic(self):
        self.assertEqual(
            web_search._search_query("Python requests timeout handling"),
            "Requests library timeout parameter",
        )

    def test_search_query_corrects_common_typo_and_resolves_elon_networth(self):
        self.assertEqual(
            web_search._search_query("elon networth"),
            "Elon Musk net worth",
        )
        self.assertEqual(
            web_search._search_query(
                "what it the dollar convertion rate in pkr"
            ),
            "USD to PKR",
        )
        self.assertEqual(web_search._search_query("USD to PKR"), "USD to PKR")

    def test_search_query_corrects_typoed_historical_list_and_currency_pair(self):
        self.assertEqual(
            web_search._search_query("pakistan presidents naem from 2000 to 2020"),
            "Pakistan presidents from 2000 to 2020",
        )
        self.assertEqual(
            web_search._search_query("curency exhcange ratebetween pkr to us"),
            "PKR to USD exchange rate today",
        )

    def test_search_intent_ignores_unrelated_previous_chat_question(self):
        query = (
            "Previous user question: what is the dollar conversion rate in PKR?\n"
            "Current question: Python requests timeout handling"
        )

        self.assertEqual(
            web_search._search_query(web_search._search_intent_text(query)),
            "Requests library timeout parameter",
        )

    def test_typo_that_looks_like_pronoun_does_not_reuse_old_context(self):
        query = (
            "Previous user question: What does the manual describe?\n"
            "Current question: what it the dollar conversion rate in pkr"
        )

        self.assertEqual(
            web_search._search_intent_text(query),
            "what it the dollar conversion rate in pkr",
        )

    def test_search_intent_resolves_referential_followup_from_previous_question(self):
        query = (
            "Previous user question: What is Elon Musk's net worth?\n"
            "Current question: What is it?"
        )

        self.assertEqual(
            web_search._search_query(web_search._search_intent_text(query)),
            "Elon Musk net worth",
        )

    def test_search_retries_temporary_provider_failures_once(self):
        unavailable = unittest.mock.Mock(status_code=503)
        unavailable.raise_for_status.return_value = None
        success = unittest.mock.Mock(status_code=200)
        success.raise_for_status.return_value = None
        request = unittest.mock.Mock(side_effect=[unavailable, success])
        with patch.object(web_search.time, "sleep"):
            response = web_search._search_request(request, "https://search.example")

        self.assertIs(response, success)
        self.assertEqual(request.call_count, 2)

    def test_authoritative_domains_are_ranked_ahead_of_general_sites(self):
        general = {
            "title": "General estimate",
            "url": "https://example.com/estimate",
            "content": "An estimate.",
            "published": "",
        }
        authoritative = {
            "title": "Published estimate",
            "url": "https://www.forbes.com/profile/elon-musk/",
            "content": "A published estimate.",
            "published": "",
        }

        ranked = web_search._rank_results([general, authoritative], limit=2)

        self.assertEqual(ranked, [authoritative, general])

    def test_authoritative_source_enrichment_extracts_relevant_page_text(self):
        response = unittest.mock.Mock()
        response.text = """Title: Requests timeouts

In Requests, the timeout parameter controls how long the request waits for a server response.

The Python client's connect timeout applies while establishing a connection.

This paragraph describes unrelated session configuration and cookies.
"""
        result = {
            "title": "Requests advanced usage",
            "url": "https://docs.python-requests.org/en/latest/user/advanced/",
            "content": "Search snippet.",
            "published": "",
        }
        with patch.object(web_search, "_search_request", return_value=response):
            enriched = web_search._enrich_search_results(
                [result],
                "Python requests timeout handling",
            )

        self.assertIn("timeout parameter controls", enriched[0]["content"])
        self.assertIn("connect timeout applies", enriched[0]["content"])
        self.assertNotIn("unrelated session configuration", enriched[0]["content"])

    def test_page_enrichment_ignores_reader_metadata_as_evidence(self):
        response = unittest.mock.Mock()
        response.text = """Title: Requests docs

URL Source: https://docs.python-requests.org/timeout

Markdown Content:

No query-relevant text is available on this page.
"""
        result = {
            "title": "Requests documentation",
            "url": "https://docs.python-requests.org/",
            "content": "Original search snippet about Requests timeouts.",
            "published": "",
        }
        with patch.object(web_search, "_search_request", return_value=response):
            enriched = web_search._enrich_search_results(
                [result],
                "Python requests timeout handling",
            )

        self.assertEqual(
            enriched[0]["content"],
            "Original search snippet about Requests timeouts.",
        )

    def test_search_results_are_cached_for_repeated_queries(self):
        results = [
            {
                "title": "Example result",
                "url": "https://example.com/result",
                "content": "A result for this cache test query.",
                "published": "",
            }
        ]
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", return_value=results) as search,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
        ):
            with web_search._search_cache_lock:
                web_search._search_cache.clear()
            first = web_search.search_online("cache test query")
            second = web_search.search_online("cache test query")

        self.assertEqual(first, second)
        search.assert_called_once_with(
            "cache test query",
            6,
            relevance_query="cache test query",
        )

    def test_brave_fallback_runs_when_list_results_are_insufficient_and_merges_sources(self):
        primary = [
            {
                "title": "Star Wars planets",
                "url": "https://example.com/planets/",
                "content": "Star Wars planets include several named worlds across the galaxy.",
                "published": "",
            }
        ]
        fallback = [
            {
                "title": "Star Wars planets reference",
                "url": "https://example.com/planets?ref=brave",
                "content": "Star Wars planets include several named worlds across the galaxy.",
                "published": "",
            },
            {
                "title": "Star Wars planets list",
                "url": "https://reference.example/planets",
                "content": "Star Wars planets include Tatooine, Hoth, Naboo, and Endor.",
                "published": "",
            },
            {
                "title": "Other Star Wars planets",
                "url": "https://encyclopedia.example/worlds",
                "content": "Star Wars planets include Coruscant and Dagobah.",
                "published": "",
            },
        ]
        metrics = {}
        with (
            patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=True),
            patch.object(web_search, "_bing_search", return_value=primary),
            patch.object(web_search, "_brave_search", return_value=fallback) as brave,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
        ):
            with web_search._search_cache_lock:
                web_search._search_cache.clear()
            results = web_search.search_online(
                "List Star Wars planets",
                limit=8,
                metrics=metrics,
            )

        brave.assert_called_once()
        self.assertEqual(len(results), 3)
        self.assertEqual(len({web_search._canonical_url(result) for result in results}), 3)
        self.assertIn("fallback_search_ms", metrics)
        self.assertEqual(metrics["result_count"], 3)

    def test_brave_is_not_called_when_primary_single_fact_evidence_is_sufficient(self):
        primary = [
            {
                "title": "Python requests timeout",
                "url": "https://docs.example/timeout",
                "content": "The Requests timeout parameter controls waiting for a server response.",
                "published": "",
            }
        ]
        with (
            patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=True),
            patch.object(web_search, "_bing_search", return_value=primary),
            patch.object(web_search, "_brave_search") as brave,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
        ):
            with web_search._search_cache_lock:
                web_search._search_cache.clear()
            results = web_search.search_online("What is the Requests timeout parameter?")

        self.assertEqual(results[0]["title"], primary[0]["title"])
        self.assertEqual(results[0]["content"], primary[0]["content"])
        self.assertEqual(results[0]["provider"], "Bing")
        self.assertGreater(results[0]["score"], 0)
        brave.assert_not_called()

    def test_brave_failure_preserves_primary_results(self):
        primary = [
            {
                "title": "Python requests timeout",
                "url": "https://docs.example/timeout",
                "content": "The Requests timeout parameter controls waiting for a server response.",
                "published": "",
            }
        ]
        with (
            patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=True),
            patch.object(web_search, "_bing_search", return_value=primary),
            patch.object(web_search, "_brave_search", side_effect=requests.Timeout("timed out")),
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
        ):
            with web_search._search_cache_lock:
                web_search._search_cache.clear()
            results = web_search.search_online("List the Requests timeout behaviors")

        self.assertEqual(results[0]["title"], primary[0]["title"])
        self.assertEqual(results[0]["content"], primary[0]["content"])
        self.assertEqual(results[0]["provider"], "Bing")

    def test_brave_fallback_recovers_when_primary_provider_fails(self):
        fallback = [
            {
                "title": "Requests timeout documentation",
                "url": "https://docs.example/requests-timeout",
                "content": "Requests exposes a timeout parameter for network operations.",
                "published": "",
            }
        ]
        metrics = {}
        with (
            patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=True),
            patch.object(web_search, "_bing_search", side_effect=requests.Timeout("offline")),
            patch.object(web_search, "_brave_search", return_value=fallback) as brave,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
        ):
            with web_search._search_cache_lock:
                web_search._search_cache.clear()
            results = web_search.search_online(
                "What is the Requests timeout parameter?",
                metrics=metrics,
            )

        self.assertEqual(results[0]["title"], fallback[0]["title"])
        self.assertEqual(results[0]["content"], fallback[0]["content"])
        self.assertEqual(results[0]["provider"], "Brave")
        brave.assert_called_once()
        self.assertEqual(metrics["primary_provider"], "Bing")
        self.assertEqual(metrics["fallback_provider"], "Brave")

    def test_brave_provider_uses_server_side_token_and_normalizes_results(self):
        response = unittest.mock.Mock()
        response.json.return_value = {
            "web": {
                "results": [
                    {
                        "title": "Requests timeout reference",
                        "url": "https://docs.example/timeout",
                        "description": "Requests exposes a timeout parameter for network operations.",
                        "page_age": "2026-01-01",
                    }
                ]
            }
        }
        with patch.object(web_search, "_search_request", return_value=response) as request:
            results = web_search._brave_search(
                "Requests timeout",
                limit=8,
                api_key="server-only-key",
                relevance_query="Requests timeout",
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["published"], "2026-01-01")
        self.assertEqual(request.call_args.args[0], web_search.requests.get)
        self.assertEqual(
            request.call_args.kwargs["headers"]["X-Subscription-Token"],
            "server-only-key",
        )
        self.assertEqual(request.call_args.kwargs["params"]["count"], 8)

    def test_insufficient_primary_evidence_detects_missing_named_entity(self):
        query = "List the presidents of France, Germany and Italy"
        results = [
            {
                "title": f"Presidents of France and Germany, reference {index}",
                "url": f"https://example{index}.com/presidents",
                "content": "A reference to presidents of France and Germany.",
                "published": "",
            }
            for index in range(3)
        ]
        self.assertEqual(web_search._requested_entities(query), ["France", "Germany", "Italy"])
        self.assertFalse(web_search._result_sufficient(query, results, intent="list"))
        results.append({
            "title": "Presidents of Italy",
            "url": "https://italy.example/presidents",
            "content": "A reference to the presidents of Italy.",
            "published": "",
        })
        self.assertTrue(web_search._result_sufficient(query, results, intent="list"))

    def test_merging_same_url_preserves_structured_currency_rate(self):
        structured = {
            "title": "PKR CHF",
            "url": "https://rates.example/pair",
            "content": "Live conversion.",
            "published": "",
            "provider": "Finance API",
            "score": 0.95,
            "structured_data": {
                "base": "PKR",
                "quote": "CHF",
                "rate": "0.0031",
                "amount": 1,
            },
        }
        longer_snippet = {
            "title": "PKR CHF conversion details",
            "url": "https://rates.example/pair?utm_source=search",
            "content": "A much longer ordinary snippet describing the conversion pair and currency rates.",
            "published": "",
            "provider": "Bing",
            "score": 0.8,
        }

        merged = web_search._merge_results(
            [structured],
            [longer_snippet],
            "PKR CHF exchange rate",
            5,
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(
            merged[0]["structured_data"]["rate"],
            "0.0031",
        )

    def test_historical_single_source_exception_requires_authority_and_date_coverage(self):
        question = "Pakistan 2000 2020 presidents"
        incomplete = {
            "title": "Pakistan Presidents",
            "url": "https://example.com/presidents",
            "content": (
                "President Pervez Musharraf and President Asif Ali Zardari are "
                "included in this summary, updated in 2026."
            ),
            "published": "",
            "provider": "Bing",
            "score": 0.8,
        }
        self.assertFalse(
            web_search._has_historical_list_coverage(question, [incomplete])
        )
        official_but_partial = {
            **incomplete,
            "url": "https://president.gov.pk/former-presidents",
            "content": "President Pervez Musharraf served 2001-2008.",
        }
        self.assertFalse(
            web_search._has_historical_list_coverage(question, [official_but_partial])
        )

    def test_list_retrieval_uses_bounded_multi_passage_local_evidence(self):
        record = {"name": "Book", "metadata": {"collection": "book_collection"}}
        documents = [f"Distinct passage {index}." for index in range(12)]
        collection = unittest.mock.Mock()
        collection.count.return_value = 20
        collection.query.return_value = {
            "documents": [documents],
            "metadatas": [[{"page": 7} for _ in documents]],
            "distances": [[0.1] * len(documents)],
        }
        client = unittest.mock.Mock()
        client.get_collection.return_value = collection
        with (
            patch.object(server, "load_catalog", return_value={"book": record}),
            patch.object(server, "normalize_catalog_record", return_value=record),
            patch.object(server.chromadb, "PersistentClient", return_value=client),
            patch.object(server, "local_embedding_function", return_value=unittest.mock.Mock()),
        ):
            passages = server._query_dataset_passages("List the main facts", "book")

        self.assertEqual(len(passages), 8)
        self.assertEqual(collection.query.call_args.kwargs["n_results"], 12)
        self.assertEqual(len({passage["text"] for passage in passages}), 8)
        long_passages = [
            {"citation": f"Page {index}", "text": "evidence " * 1000}
            for index in range(8)
        ]
        self.assertLessEqual(len(server._format_passages(long_passages)), 6500)

    def test_web_evidence_context_honors_configured_character_bound(self):
        results = [
            {
                "title": f"Result {index}",
                "url": f"https://example{index}.com/",
                "content": "Relevant evidence " * 500,
                "published": "",
            }
            for index in range(8)
        ]
        self.assertLessEqual(len(server.format_web_results(results, max_chars=2500)), 2500)

    def test_local_list_answer_uses_intent_prompt_and_reports_completeness(self):
        context = "[Book: Page 1]\nFirst supported item.\n\n[Book: Page 2]\nSecond supported item."
        with (
            patch.object(server, "local_context", return_value=context),
            patch.object(server, "generate_reply", return_value="- First item\n- Second item") as generate,
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "List the two supported items.",
                    "search_mode": "local",
                    "dataset_ids": ["book"],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate.call_args.kwargs["question_intent"], "list")
        self.assertTrue(response.json()["metrics"]["answer_completeness"]["complete"])
        self.assertEqual(response.json()["metrics"]["question_type"], "list")

    def test_list_generation_uses_complete_list_instructions(self):
        response = unittest.mock.Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "- First item\n- Second item"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 12},
        }
        response.raise_for_status.return_value = None
        with patch.object(server.requests, "post", return_value=response) as post:
            server.generate_reply(
                "List the supported items.",
                "[Book: Page 1]\nFirst item.\n\n[Book: Page 2]\nSecond item.",
                False,
                "book",
                question_intent="list",
            )

        system_prompt = post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertIn("complete readable list", system_prompt)
        self.assertIn("do not stop at the first matching item", system_prompt)

    def test_rejects_irrelevant_or_non_https_results(self):
        response = unittest.mock.Mock()
        response.text = """Title: Search results - Bing
## [Search Help](https://example.com/help)

Help with browser settings.
## [Elon Musk Net Worth](http://example.com/elon)

Current estimate of Elon Musk net worth.
"""
        response.raise_for_status.return_value = None
        with patch.object(web_search.requests, "get", return_value=response):
            self.assertEqual(web_search._bing_search("Elon Musk net worth", limit=5), [])

    def test_relevance_rejects_region_maps_without_president_evidence(self):
        result = {
            "title": "Map of Africa - List of African Countries",
            "url": "https://example.com/africa-countries",
            "content": "Countries of Africa listed alphabetically.",
            "published": "",
        }
        self.assertFalse(
            web_search._relevant("presidents of African countries list", result)
        )

    def test_bing_search_decodes_search_redirects_to_real_source_links(self):
        source_url = "https://www.forbes.com/profile/elon-musk/"
        encoded_url = base64.urlsafe_b64encode(source_url.encode("utf-8")).decode().rstrip("=")
        response = unittest.mock.Mock()
        response.text = f"""Title: Elon Musk net worth - Bing
## [**Elon Musk** - **Forbes**](https://www.bing.com/ck/a?u=a1{encoded_url})

Elon Musk is tracked on the Forbes real-time billionaires list.
"""
        with patch.object(web_search.requests, "get", return_value=response):
            results = web_search._bing_search("Elon Musk net worth Forbes", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], source_url)
        self.assertIn("Forbes real-time", results[0]["content"])

    def test_web_search_fails_instead_of_returning_unrelated_results(self):
        metrics = {}
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", return_value=[]),
        ):
            results = web_search.search_online(
                "current net worth of Elon Musk",
                metrics=metrics,
            )

        self.assertEqual(results, [])
        self.assertEqual(metrics["primary_status"], "empty")
        self.assertEqual(metrics["final_result_count"], 0)

    def test_web_only_mode_returns_sources_without_using_local_dataset(self):
        results = [
            {
                "title": "Elon Musk - Forbes",
                "url": "https://www.forbes.com/profile/elon-musk/",
                "content": "Forbes tracks Elon Musk's estimated net worth.",
                "published": "Wed, 30 Sep 2026",
            }
        ]
        with (
            patch.object(server, "search_online", return_value=results),
            patch.object(server, "local_context") as local_context,
            patch.object(server, "generate_reply", return_value="Forbes lists an estimate [1].") as generate,
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "What is Elon Musk's net worth?",
                    "search_mode": "web",
                    "collection": "data_history",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sources"], results)
        local_context.assert_not_called()
        self.assertIn("LIVE WEB SEARCH RESULTS", generate.call_args.args[1])
        self.assertEqual(generate.call_args.kwargs["mixed"], False)

    def test_unrelated_prior_turn_is_not_added_to_web_query_or_answer_context(self):
        results = [
            {
                "title": "Requests documentation",
                "url": "https://docs.python-requests.org/",
                "content": "Requests supports timeouts.",
                "published": "",
            }
        ]
        history = [
            {"role": "user", "content": "What is the dollar conversion rate in PKR?"},
            {"role": "assistant", "content": "The search failed."},
        ]
        with (
            patch.object(server, "search_online", return_value=results) as search,
            patch.object(server, "generate_reply", return_value="Use the timeout parameter [1].") as generate,
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "Python requests timeout handling",
                    "search_mode": "web",
                    "conversation_history": history,
                },
            )

        self.assertEqual(response.status_code, 200)
        search.assert_called_once()
        self.assertEqual(search.call_args.args[0], "Python requests timeout handling")
        self.assertEqual(search.call_args.kwargs["intent"], "research/web")
        self.assertEqual(generate.call_args.kwargs["conversation_history"], [])

    def test_web_search_failure_degrades_to_selected_local_dataset(self):
        with (
            patch.object(server, "search_online", side_effect=requests.Timeout("offline")),
            patch.object(server, "local_context", return_value="[Page 7]\nKnown local fact."),
            patch.object(server, "generate_reply", return_value="Known local fact [Page 7].") as generate,
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "What is the known local fact?",
                    "search_mode": "web",
                    "dataset_ids": ["local-book"],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["metrics"]["degraded_to_local"])
        self.assertEqual(response.json()["sources"], [])
        self.assertEqual(generate.call_args.args[1], "[Page 7]\nKnown local fact.")
        self.assertFalse(generate.call_args.args[2])

    def test_mixed_mode_uses_both_local_context_and_live_web_results(self):
        results = [
            {
                "title": "Current report",
                "url": "https://example.com/report",
                "content": "Latest report evidence.",
                "published": "",
            }
        ]
        with (
            patch.object(server, "search_online", return_value=results),
            patch.object(server, "local_context", return_value="[Page 4]\nBook evidence."),
            patch.object(server, "generate_reply", return_value="Combined answer [1] [Page 4].") as generate,
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "question",
                    "search_mode": "mixed",
                    "collection": "data_manual",
                },
            )

        self.assertEqual(response.status_code, 200)
        context = generate.call_args.args[1]
        self.assertIn("Book evidence.", context)
        self.assertIn("Latest report evidence.", context)
        self.assertTrue(generate.call_args.kwargs["mixed"])

    def test_multiple_dataset_ids_are_queried_and_combined_by_relevance(self):
        with (
            patch.object(server, "load_catalog", return_value={"data_manual": {}, "data_history": {}}),
            patch.object(
                server,
                "_query_dataset_passages",
                side_effect=lambda prompt, dataset_id: [
                    {
                        "text": f"Evidence from {dataset_id}.",
                        "citation": dataset_id,
                        "score": 0.9 if dataset_id == "data_history" else 0.2,
                        "rank": 0,
                    }
                ],
            ) as query_dataset,
        ):
            context = server.local_context_for_datasets(
                "question",
                ["data_manual", "data_history"],
            )

        self.assertLess(context.index("[data_history]"), context.index("[data_manual]"))
        self.assertEqual(query_dataset.call_count, 2)

    def test_local_and_api_catalog_datasets_can_be_selected_together(self):
        with (
            patch.object(server, "load_catalog", return_value={"local_manual": {}, "api_docs": {}}),
            patch.object(
                server,
                "_query_dataset_passages",
                side_effect=lambda prompt, dataset_id: [
                    {
                        "text": f"Evidence from {dataset_id}.",
                        "citation": dataset_id,
                        "score": 0.8,
                        "rank": 0,
                    }
                ],
            ),
        ):
            context = server.local_context_for_datasets(
                "question",
                ["local_manual", "api_docs"],
            )

        self.assertIn("[api_docs]", context)
        self.assertIn("Evidence from api_docs.", context)

    def test_ask_accepts_dataset_id_list_and_generates_one_answer(self):
        with (
            patch.object(
                server,
                "local_context_for_datasets",
                return_value="[History]\nHistory evidence.\n\n[Aircraft]\nAircraft evidence.",
            ) as local_context,
            patch.object(server, "generate_reply", return_value="Unified answer.") as generate,
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "Question",
                    "search_mode": "local",
                    "dataset_ids": ["history_archive_v1", "manual_docs"],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "Unified answer.")
        local_context.assert_called_once_with(
            "Question",
            ["history_archive_v1", "manual_docs"],
        )
        self.assertIn("History evidence.", generate.call_args.args[1])
        self.assertIn("Aircraft evidence.", generate.call_args.args[1])

    def test_ask_forwards_answer_customization_to_generation(self):
        with (
            patch.object(server, "local_context", return_value="Evidence."),
            patch.object(server, "generate_reply", return_value="Answer.") as generate,
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "Question",
                    "search_mode": "local",
                    "collection": "local_manual",
                    "temperature": 0.6,
                    "answer_style": "balanced",
                    "answer_instructions": "Define abbreviations.",
                    "model_id": "custom/model-v2",
                    "max_tokens": 1024,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate.call_args.kwargs["temperature"], 0.6)
        self.assertEqual(generate.call_args.kwargs["answer_style"], "balanced")
        self.assertEqual(
            generate.call_args.kwargs["answer_instructions"],
            "Define abbreviations.",
        )
        self.assertEqual(generate.call_args.kwargs["model_id"], "custom/model-v2")
        self.assertEqual(generate.call_args.kwargs["max_tokens"], 1024)

    def test_ask_uses_recent_turns_for_followup_retrieval_and_model_context(self):
        history = [
            {"role": "user", "content": "What does the manual describe?"},
            {"role": "assistant", "content": "It described the F-16 [Page 4]."},
        ]
        with (
            patch.object(server, "local_context", return_value="[Page 4]\nF-16 evidence.") as local_context,
            patch.object(server, "generate_reply", return_value="It is a multirole fighter.") as generate,
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "What role does it have?",
                    "search_mode": "local",
                    "dataset_ids": ["local_manual"],
                    "conversation_history": history,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Previous user question: What does the manual describe?", local_context.call_args.args[0])
        self.assertIn("Current question: What role does it have?", local_context.call_args.args[0])
        self.assertEqual(generate.call_args.args[0], "What role does it have?")
        self.assertEqual(generate.call_args.kwargs["conversation_history"][1].content, "It described the F-16 [Page 4].")

    def test_ask_rejects_oversized_conversation_history(self):
        response = TestClient(server.app).post(
            "/ask",
            json={
                "prompt": "Question",
                "conversation_history": [
                    {"role": "user", "content": f"Turn {index}"}
                    for index in range(11)
                ],
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_no_relevant_web_results_never_reach_the_chat_model(self):
        with (
            patch.object(server, "search_online", side_effect=ValueError("No relevant results")),
            patch.object(server, "generate_reply") as generate,
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={"prompt": "question", "search_mode": "web"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("could not retrieve enough", response.json()["reply"].lower())
        self.assertFalse(response.json()["metrics"]["model_generated"])
        generate.assert_not_called()

    def test_search_network_errors_are_reported_to_client(self):
        with patch.object(
            server,
            "search_online",
            side_effect=requests.Timeout("Search timed out"),
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={"prompt": "question", "search_mode": "web"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("could not retrieve enough", response.json()["reply"].lower())
        self.assertFalse(response.json()["metrics"]["model_generated"])
        self.assertEqual(response.json()["metrics"]["error_type"], "Timeout")

    def test_legacy_web_search_flag_still_selects_web_only(self):
        results = [
            {
                "title": "Current report",
                "url": "https://example.com/report",
                "content": "A current report.",
                "published": "",
            }
        ]
        with (
            patch.object(server, "search_online", return_value=results),
            patch.object(server, "local_context") as local_context,
            patch.object(server, "generate_reply", return_value="Answer [1]."),
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={"prompt": "question", "search_web": True},
            )

        self.assertEqual(response.status_code, 200)
        local_context.assert_not_called()


if __name__ == "__main__":
    unittest.main()
