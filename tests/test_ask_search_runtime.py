import unittest
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient

import server
import web_search
from query_intent import LARGE_LIST, LIST, LIVE_MARKET, classify_question


class AskSearchRuntimeTests(unittest.TestCase):
    def setUp(self):
        with web_search._search_cache_lock:
            web_search._search_cache.clear()

    def post_ask(self, prompt, **payload):
        return TestClient(server.app).post(
            "/ask",
            json={"prompt": prompt, "search_mode": "web", **payload},
        )

    @staticmethod
    def result(title, url, content, published=""):
        return {
            "title": title,
            "url": url,
            "content": content,
            "published": published,
        }

    def test_empty_primary_results_call_brave_through_ask_and_answer(self):
        primary = []
        fallback = [
            self.result(
                "Python timeout documentation",
                "https://docs.example/python-timeout",
                "Python requests support a timeout parameter for HTTP requests.",
            )
        ]
        with (
            patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=True),
            patch.object(web_search, "_bing_search", return_value=primary) as bing,
            patch.object(web_search, "_brave_search", return_value=fallback) as brave,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server, "generate_reply", return_value="Use the timeout parameter [1].") as generate,
        ):
            response = self.post_ask("What is the Python requests timeout parameter?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "Use the timeout parameter [1].")
        bing.assert_called_once()
        brave.assert_called_once()
        self.assertIn("Python timeout documentation", generate.call_args.args[1])
        self.assertEqual(response.json()["metrics"]["fallback_result_count"], 1)

    def test_provider_no_results_exception_is_caught_before_brave_fallback(self):
        fallback = [
            self.result(
                "Python timeout documentation",
                "https://docs.example/python-timeout",
                "Python requests support a timeout parameter for HTTP requests.",
            )
        ]
        for failure in (ValueError("Bing returned no search results"),):
            with self.subTest(failure=failure):
                with (
                    patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=True),
                    patch.object(web_search, "_bing_search", side_effect=failure),
                    patch.object(web_search, "_brave_search", return_value=fallback) as brave,
                    patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
                    patch.object(server, "generate_reply", return_value="Found evidence [1]."),
                ):
                    response = self.post_ask("What is the Python requests timeout parameter?")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["metrics"]["primary_status"], "error")
            brave.assert_called_once()

    def test_primary_timeout_is_caught_before_brave_fallback(self):
        fallback = [
            self.result(
                "Python timeout documentation",
                "https://docs.example/python-timeout",
                "Python requests support a timeout parameter for HTTP requests.",
            )
        ]
        with (
            patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=True),
            patch.object(web_search, "_bing_search", side_effect=requests.Timeout("timeout")),
            patch.object(web_search, "_brave_search", return_value=fallback) as brave,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server, "generate_reply", return_value="Found evidence [1]."),
        ):
            response = self.post_ask("What is the Python requests timeout parameter?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["primary_status"], "error")
        self.assertEqual(response.json()["metrics"]["fallback_status"], "success")
        brave.assert_called_once()

    def test_good_primary_results_skip_brave_through_ask(self):
        primary = [
            self.result(
                f"Python timeout documentation {index}",
                f"https://docs{index}.example/python-timeout",
                "Python requests support a timeout parameter for HTTP requests.",
            )
            for index in range(3)
        ]
        with (
            patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=True),
            patch.object(web_search, "_bing_search", return_value=primary),
            patch.object(web_search, "_brave_search") as brave,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server, "generate_reply", return_value="Use a timeout [1]."),
        ):
            response = self.post_ask("What is the Python requests timeout parameter?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["primary_status"], "success")
        self.assertEqual(response.json()["metrics"]["fallback_result_count"], 0)
        brave.assert_not_called()

    def test_empty_primary_and_fallback_return_controlled_insufficient_evidence(self):
        with (
            patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=True),
            patch.object(web_search, "_bing_search", return_value=[]),
            patch.object(web_search, "_brave_search", return_value=[]),
            patch.object(server, "generate_reply") as generate,
        ):
            response = self.post_ask("What is the Python requests timeout parameter?")

        self.assertEqual(response.status_code, 200)
        self.assertIn("could not retrieve enough", response.json()["reply"].lower())
        self.assertEqual(response.json()["metrics"]["final_result_count"], 0)
        self.assertFalse(response.json()["metrics"]["model_generated"])
        self.assertNotIn("Bing returned", response.json()["reply"])
        generate.assert_not_called()

    def test_elonnetworth_is_normalized_and_metrics_preserve_original_query(self):
        primary = [
            self.result(
                "Elon Musk net worth",
                "https://finance.example/elon-musk",
                "Elon Musk's net worth is estimated in current financial rankings.",
            )
            for _ in range(3)
        ]
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", return_value=primary) as bing,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server, "generate_reply", return_value="See the estimate [1]."),
        ):
            response = self.post_ask("elonnetworth")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(bing.call_args.args[0], "Elon Musk net worth")
        metrics = response.json()["metrics"]
        self.assertEqual(metrics["original_query"], "elonnetworth")
        self.assertEqual(metrics["normalized_query"], "Elon Musk net worth")
        self.assertEqual(metrics["primary_provider"], "Bing")
        self.assertTrue(metrics["model_generated"])

    def test_currency_query_is_expanded_and_does_not_use_local_chroma(self):
        results = [
            self.result(
                f"PKR to CHF exchange rate today {index}",
                f"https://rates{index}.example/pkr-chf",
                "PKR to CHF exchange rate today, Swiss franc conversion quote.",
            )
            for index in range(3)
        ]
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", return_value=results) as bing,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server, "local_context") as local_context,
            patch.object(server, "generate_reply", return_value="The current rate is cited [1]."),
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "current exchange rate between pkr to swiss currency",
                    "search_mode": "local",
                    "dataset_ids": ["stale-book"],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(bing.call_args.args[0], "PKR to CHF exchange rate today")
        self.assertEqual(response.json()["metrics"]["intent"], "current_web")
        self.assertTrue(response.json()["metrics"]["web_forced"])
        local_context.assert_not_called()

    def test_typoed_currency_query_forces_live_search_and_expands_us_to_usd(self):
        results = [
            self.result(
                f"PKR to USD exchange rate today {index}",
                f"https://rates{index}.example/pkr-usd",
                "PKR to USD exchange rate is 0.0036 today.",
            )
            for index in range(3)
        ]
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", return_value=results) as bing,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server, "local_context") as local_context,
            patch.object(server, "generate_reply", return_value="1 PKR is 0.0036 USD [1]."),
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "curency exhcange ratebetween pkr to us",
                    "search_mode": "local",
                    "dataset_ids": ["stale-book"],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(bing.call_args.args[0], "PKR to USD exchange rate today")
        self.assertEqual(response.json()["metrics"]["intent"], "current_web")
        self.assertTrue(response.json()["metrics"]["web_forced"])
        self.assertEqual(
            response.json()["metrics"]["normalized_query"],
            "PKR to USD exchange rate today",
        )
        self.assertTrue(response.json()["metrics"]["model_generated"])
        local_context.assert_not_called()

    def test_typoed_historical_president_query_uses_targeted_web_search(self):
        results = [
            self.result(
                f"Pakistan presidents from 2000 to 2020 source {index}",
                f"https://history{index}.example/pakistan-presidents",
                (
                    f"Pakistan president Pervez Musharraf served from 2001 to 2008. "
                    f"Historical presidents timeline source {index}."
                ),
            )
            for index in range(3)
        ]
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", return_value=results) as bing,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server, "generate_reply", return_value="- Pervez Musharraf [1]\n- Asif Ali Zardari [2]") as generate,
        ):
            response = self.post_ask(
                "pakistan presidents naem from 2000 to 2020"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["intent"], LIST)
        self.assertEqual(
            response.json()["metrics"]["normalized_query"],
            "Pakistan presidents from 2000 to 2020",
        )
        self.assertEqual(
            bing.call_args_list[0].args[0],
            "Pakistan presidents from 2000 to 2020",
        )
        self.assertEqual(
            bing.call_args_list[1].args[0],
            "Pakistan former presidents 2000 2020",
        )
        self.assertTrue(response.json()["metrics"]["model_generated"])
        self.assertIn("Pakistan presidents", generate.call_args.args[1])

    def test_currency_results_missing_chf_are_rejected_before_qwen(self):
        usd_results = [
            self.result(
                f"PKR to USD exchange rate {index}",
                f"https://usd{index}.example/pkr-usd",
                "PKR to USD exchange rate today, Pakistani rupee conversion quote.",
            )
            for index in range(3)
        ]
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", return_value=usd_results),
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server, "local_context") as local_context,
            patch.object(server, "generate_reply") as generate,
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "current exchange rate between pkr to swiss currency",
                    "search_mode": "local",
                    "dataset_ids": ["stale-book"],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("could not retrieve enough", response.json()["reply"].lower())
        self.assertEqual(
            response.json()["metrics"]["insufficiency_reason"],
            "currency result did not contain a verified rate for the requested pair",
        )
        self.assertEqual(response.json()["metrics"]["primary_result_count"], 3)
        self.assertEqual(response.json()["metrics"]["final_result_count"], 0)
        local_context.assert_not_called()
        generate.assert_not_called()

    def test_historical_presidents_list_passes_multiple_sources_to_qwen(self):
        results = [
            self.result(
                f"Pakistan presidents 2000 2020 source {index}",
                f"https://history{index}.example/pakistan-presidents",
                f"Pakistan presidents from 2000 to 2020. Historical source {index}.",
            )
            for index in range(3)
        ]
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", return_value=results) as bing,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server, "generate_reply", return_value="- President [1]\n- President [2]") as generate,
        ):
            response = self.post_ask("Who were the presidents of Pakistan from 2000 to 2020?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["intent"], LIST)
        self.assertEqual(bing.call_count, 2)
        context = generate.call_args.args[1]
        self.assertGreaterEqual(context.count("Evidence:"), 3)

    def test_single_authoritative_historical_list_source_passes_evidence_gate(self):
        official = self.result(
            "Former Presidents of Pakistan",
            "https://president.gov.pk/former-presidents",
            (
                "President Pervez Musharraf served from 2001 to 2008. "
                "President Asif Ali Zardari served from 2008 to 2013. "
                "President Mamnoon Hussain served from 2013 to 2018. "
                "President Arif Alvi served from 2018 to 2020. "
                "Official Government of Pakistan presidential history."
            ),
        )
        model_response = unittest.mock.Mock()
        model_response.json.return_value = {
            "choices": [{"message": {"content": "Musharraf, Zardari, Hussain and Alvi [1]."}}],
            "usage": {"prompt_tokens": 90, "completion_tokens": 15},
        }
        model_response.raise_for_status.return_value = None
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", return_value=[official]),
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server.requests, "post", return_value=model_response) as model,
            self.assertLogs("web_search", level="INFO") as search_logs,
        ):
            response = self.post_ask(
                "Who were the presidents of Pakistan from 2000 to 2020?"
            )

        self.assertEqual(response.status_code, 200)
        metrics = response.json()["metrics"]
        self.assertTrue(metrics["evidence_sufficient"])
        self.assertTrue(metrics["model_generated"])
        self.assertEqual(metrics["final_result_count"], 1)
        prompt = model.call_args.kwargs["json"]["messages"][-1]["content"]
        self.assertIn("Former Presidents of Pakistan", prompt)
        self.assertIn("President Arif Alvi served from 2018 to 2020", prompt)
        logs = "\n".join(search_logs.output)
        self.assertIn("[EVIDENCE_GATE]", logs)
        self.assertIn("provider=Bing", logs)
        self.assertIn("president.gov.pk", logs)
        self.assertIn("President Pervez Musharraf", logs)
        self.assertIn("score=", logs)

    def test_structured_currency_rate_is_normalized_and_formatted_for_qwen(self):
        structured_result = {
            "title": "PKR to CHF live conversion",
            "url": "https://rates.example/convert/PKR/CHF",
            "description": "Live exchange-rate quote.",
            "provider": "mock-finance",
            "score": 0.97,
            "data": {
                "result": "success",
                "base_code": "PKR",
                "conversion_rates": {"CHF": "0.0031"},
                "time_last_update_utc": "2026-10-02T03:45:00Z",
            },
        }
        model_response = unittest.mock.Mock()
        model_response.json.return_value = {
            "choices": [{"message": {"content": "1 PKR equals 0.0031 CHF as of the update [1]."}}],
            "usage": {"prompt_tokens": 80, "completion_tokens": 16},
        }
        model_response.raise_for_status.return_value = None
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", return_value=[structured_result]),
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server.requests, "post", return_value=model_response) as model,
            self.assertLogs("web_search", level="INFO") as search_logs,
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "current exchange rate between pkr to swiss currency",
                    "search_mode": "local",
                    "dataset_ids": ["stale-book"],
                },
            )

        self.assertEqual(response.status_code, 200)
        metrics = response.json()["metrics"]
        self.assertTrue(metrics["evidence_sufficient"])
        self.assertTrue(metrics["model_generated"])
        source = response.json()["sources"][0]
        self.assertEqual(source["structured_data"]["base"], "PKR")
        self.assertEqual(source["structured_data"]["quote"], "CHF")
        model_context = model.call_args.kwargs["json"]["messages"][-1]["content"]
        self.assertIn("Structured data: 1 PKR = 0.0031 CHF", model_context)
        self.assertIn("2026-10-02T03:45:00Z", model_context)
        self.assertIn("Evidence: Live exchange-rate quote.", model_context)
        logs = "\n".join(search_logs.output)
        self.assertIn("provider=Bing", logs)
        self.assertIn("title='PKR to CHF live conversion'", logs)
        self.assertIn("rates.example/convert/PKR/CHF", logs)
        self.assertIn("snippet='Live exchange-rate quote.", logs)
        self.assertIn("score=0.97", logs)
        self.assertIn("result_count=1", logs)

    def test_profitted_stock_query_forces_live_market_and_never_uses_local_data(self):
        results = [
            self.result(
                f"Top gaining stocks today source {index}",
                f"https://market{index}.example/gainers",
                "Top gaining stocks today as of 2026-10-02 market close timestamp.",
                "2026-10-02",
            )
            for index in range(3)
        ]
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", return_value=results) as bing,
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server, "local_context") as local_context,
            patch.object(server, "generate_reply", return_value="The source lists current gainers [1]."),
        ):
            response = TestClient(server.app).post(
                "/ask",
                json={
                    "prompt": "what is the most profitted stock of the day",
                    "search_mode": "local",
                    "dataset_ids": ["stale-book"],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(bing.call_args.args[0], "top gaining stocks today")
        self.assertEqual(response.json()["metrics"]["intent"], LIVE_MARKET)
        self.assertTrue(response.json()["metrics"]["web_forced"])
        local_context.assert_not_called()

    def test_large_all_countries_list_uses_five_bounded_region_searches(self):
        calls = []

        def primary_search(query, limit, relevance_query=None):
            calls.append(query)
            region = query.rsplit(" ", 1)[-1]
            index = len(calls)
            return [
                self.result(
                    f"Presidents in {region}",
                    f"https://region{index}.example/{region.lower()}",
                    f"Current presidents of countries in {region}, evidence source.",
                )
            ]

        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(web_search, "_bing_search", side_effect=primary_search),
            patch.object(web_search, "_enrich_search_results", side_effect=lambda found, query, **kwargs: found),
            patch.object(server, "generate_reply", return_value="A region-by-region list [1]."),
        ):
            response = self.post_ask("name all the presidents of all countries")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(calls), 5)
        self.assertEqual(response.json()["metrics"]["intent"], LARGE_LIST)
        self.assertEqual(
            set(response.json()["metrics"]["region_coverage"]),
            {"Africa", "Asia", "Europe", "Americas", "Oceania"},
        )
        self.assertEqual(response.json()["metrics"]["missing_regions"], [])

    def test_intent_classifier_prioritizes_current_market_and_worldwide_lists(self):
        self.assertEqual(
            classify_question("what is the most profitted stock of the day"),
            LIVE_MARKET,
        )
        self.assertEqual(classify_question("name all the presidents of all countries"), LARGE_LIST)


if __name__ == "__main__":
    unittest.main()
