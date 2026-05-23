import os
import tempfile
import unittest

from db import database


class DatabaseRunsTest(unittest.TestCase):
    def test_run_and_ai_call_tables_are_created_and_writable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_path = database.DB_PATH
            database.DB_PATH = os.path.join(tmpdir, "radar.db")
            try:
                database.init_db()
                run_id = database.create_run(
                    source="test",
                    keyword="need a tool",
                    subreddit="SideProject",
                    limit_count=2,
                )
                database.add_run_post(run_id, "abc")
                call_id = database.start_ai_call(
                    run_id,
                    "abc",
                    "filter",
                    "deepseek-chat",
                    prompt_chars=123,
                )
                database.finish_ai_call(
                    call_id,
                    "success",
                    attempt_count=1,
                    response_text='{"ok": true}',
                    duration_ms=20,
                )
                database.record_analysis_result(
                    run_id,
                    "abc",
                    "filter",
                    {"total": 7.0, "one_line_summary": "测试摘要"},
                )

                self.assertEqual(database.get_run_reddit_ids(run_id), ["abc"])
            finally:
                database.DB_PATH = old_path


if __name__ == "__main__":
    unittest.main()
