import unittest

from query_intent import (
    LIST,
    MULTI_PART,
    RESEARCH_WEB,
    SINGLE_FACT,
    check_answer_completeness,
    classify_question,
    retrieval_limits,
)


class QueryIntentTests(unittest.TestCase):
    def test_classifies_single_fact_list_multi_part_and_web_research(self):
        self.assertEqual(classify_question("When was the first flight?"), SINGLE_FACT)
        self.assertEqual(classify_question("Who were the presidents of Pakistan?"), LIST)
        self.assertEqual(
            classify_question("pakistan presidents naem from 2000 to 2020"),
            LIST,
        )
        self.assertEqual(
            classify_question("curency exhcange ratebetween pkr to us"),
            "current_web",
        )
        self.assertEqual(classify_question("What is X? Also, why did Y happen?"), MULTI_PART)
        self.assertEqual(classify_question("When was the election?", web=True), RESEARCH_WEB)
        self.assertEqual(classify_question("List the presidents.", web=True), LIST)

    def test_retrieval_limits_are_bounded_and_scale_for_multi_item_queries(self):
        self.assertEqual(retrieval_limits(SINGLE_FACT), (6, 3))
        self.assertEqual(retrieval_limits(LIST), (12, 8))
        self.assertEqual(retrieval_limits(MULTI_PART), (12, 8))
        self.assertEqual(retrieval_limits(RESEARCH_WEB), (12, 10))

    def test_completeness_check_flags_unstructured_list_answer(self):
        result = check_answer_completeness(
            "List the main types.",
            LIST,
            "[Source A]\nFirst item.\n\n[Source B]\nSecond item.",
            "The first item is supported by the sources.",
        )
        self.assertFalse(result["complete"])
        self.assertEqual(result["evidence_blocks"], 2)

    def test_completeness_check_accepts_structured_answer(self):
        result = check_answer_completeness(
            "List the main types.",
            LIST,
            "[Source A]\nFirst item.\n\n[Source B]\nSecond item.",
            "- First item\n- Second item",
        )
        self.assertTrue(result["complete"])
        self.assertEqual(result["answer_items"], 2)


if __name__ == "__main__":
    unittest.main()
