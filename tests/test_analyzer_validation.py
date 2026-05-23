import unittest
from unittest.mock import Mock, patch

from ai import analyzer


class AnalyzerValidationTest(unittest.TestCase):
    def test_filter_result_validation_accepts_expected_schema(self):
        result = analyzer.validate_filter_result({
            "pain_clarity": 8,
            "frequency": 6,
            "actionability": 7,
            "total": 7.1,
            "one_line_summary": "用户需要更好的工具",
            "confidence": "high",
        })

        self.assertEqual(result["total"], 7.1)
        self.assertEqual(result["confidence"], "high")

    def test_filter_result_validation_rejects_missing_required_text(self):
        with self.assertRaises(ValueError):
            analyzer.validate_filter_result({
                "pain_clarity": 8,
                "frequency": 6,
                "actionability": 7,
                "total": 7.1,
                "one_line_summary": "",
                "confidence": "high",
            })

    def test_insight_result_validation_normalizes_expected_fields(self):
        result = analyzer.validate_insight_result({
            "pain_point": "用户整理 Reddit 需求很费时间",
            "user_quote": "I need a better way to find ideas",
            "target_audience": "独立开发者",
            "project_idea": "做一个本地需求雷达",
            "difficulty": 2,
            "opensource_value": "medium",
            "opensource_reason": "有学习价值",
            "monetize_potential": "low",
            "monetize_reason": "付费意愿不确定",
            "beginner_difficulty": 2,
            "free_build_possible": "yes",
            "beginner_reason": "可以用免费工具做 MVP",
            "confidence": "medium",
        })

        self.assertEqual(result["difficulty"], 2)
        self.assertEqual(result["free_build_possible"], "yes")

    def test_create_ai_client_reads_key_at_call_time(self):
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "dynamic-key"}):
            with patch("ai.analyzer.OpenAI") as openai_mock:
                analyzer.create_ai_client()

        openai_mock.assert_called_once()
        self.assertEqual(openai_mock.call_args.kwargs["api_key"], "dynamic-key")

    @patch("ai.analyzer.time.sleep")
    @patch("db.database.finish_ai_call")
    @patch("db.database.start_ai_call")
    def test_call_deepseek_records_ai_call_success(
        self,
        start_ai_call_mock,
        finish_ai_call_mock,
        sleep_mock,
    ):
        start_ai_call_mock.return_value = "call-1"
        client = Mock()
        client.chat.completions.create.return_value.choices = [
            Mock(message=Mock(content='{"ok": true}'))
        ]

        content = analyzer.call_deepseek(
            client,
            "system",
            "user",
            model="deepseek-chat",
            source_run_id="run-1",
            reddit_id="abc",
            stage="filter",
        )

        self.assertEqual(content, '{"ok": true}')
        start_ai_call_mock.assert_called_once()
        finish_ai_call_mock.assert_called_once()
        self.assertEqual(finish_ai_call_mock.call_args.kwargs["status"], "success")


if __name__ == "__main__":
    unittest.main()
