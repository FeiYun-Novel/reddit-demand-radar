import unittest
from unittest.mock import Mock, patch

from pipeline.service import clamp_limit, run_pipeline


class PipelineServiceTest(unittest.TestCase):
    def test_clamp_limit_handles_bad_and_out_of_range_values(self):
        self.assertEqual(clamp_limit(None), 30)
        self.assertEqual(clamp_limit("bad"), 30)
        self.assertEqual(clamp_limit(-5), 1)
        self.assertEqual(clamp_limit(999), 100)
        self.assertEqual(clamp_limit("12"), 12)

    @patch("pipeline.service.run_analysis")
    @patch("pipeline.service.update_run")
    @patch("pipeline.service.add_run_posts")
    @patch("pipeline.service.create_run")
    @patch("pipeline.service.init_db")
    @patch("pipeline.service.scrape_and_save")
    @patch("pipeline.service.create_reddit_client")
    def test_empty_scrape_skips_ai_analysis(
        self,
        create_reddit_client,
        scrape_and_save,
        init_db_mock,
        create_run_mock,
        add_run_posts_mock,
        update_run_mock,
        run_analysis_mock,
    ):
        create_reddit_client.return_value = object()
        create_run_mock.return_value = "run-1"
        scrape_and_save.return_value = {
            "keyword": "need a tool",
            "subreddit": "SideProject",
            "fetched": 0,
            "new": 0,
            "skipped": 0,
            "reddit_ids": [],
        }

        stats = run_pipeline("need a tool", "SideProject", 10)

        run_analysis_mock.assert_not_called()
        create_run_mock.assert_called_once()
        add_run_posts_mock.assert_called_once_with("run-1", [])
        self.assertEqual(stats["analyzed"], 0)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["run_id"], "run-1")

    @patch("pipeline.service.run_analysis")
    @patch("pipeline.service.update_run")
    @patch("pipeline.service.add_run_posts")
    @patch("pipeline.service.create_run")
    @patch("pipeline.service.init_db")
    @patch("pipeline.service.scrape_and_save")
    @patch("pipeline.service.create_reddit_client")
    def test_cancel_after_scrape_skips_ai_analysis(
        self,
        create_reddit_client,
        scrape_and_save,
        init_db_mock,
        create_run_mock,
        add_run_posts_mock,
        update_run_mock,
        run_analysis_mock,
    ):
        create_reddit_client.return_value = object()
        create_run_mock.return_value = "run-2"
        scrape_and_save.return_value = {
            "keyword": "need a tool",
            "subreddit": "SideProject",
            "fetched": 1,
            "new": 1,
            "skipped": 0,
            "reddit_ids": ["abc123"],
        }

        stats = run_pipeline(
            "need a tool",
            "SideProject",
            10,
            cancel_check=Mock(return_value=True),
        )

        run_analysis_mock.assert_not_called()
        self.assertTrue(stats["cancelled"])
        self.assertEqual(stats["reddit_ids"], ["abc123"])
        self.assertEqual(stats["run_id"], "run-2")

    @patch("pipeline.service.run_analysis")
    @patch("pipeline.service.update_run")
    @patch("pipeline.service.add_run_posts")
    @patch("pipeline.service.create_run")
    @patch("pipeline.service.init_db")
    @patch("pipeline.service.scrape_and_save")
    @patch("pipeline.service.create_reddit_client")
    def test_scrape_batch_is_passed_to_analysis(
        self,
        create_reddit_client,
        scrape_and_save,
        init_db_mock,
        create_run_mock,
        add_run_posts_mock,
        update_run_mock,
        run_analysis_mock,
    ):
        create_reddit_client.return_value = object()
        create_run_mock.return_value = "run-3"
        scrape_and_save.return_value = {
            "keyword": "need a tool",
            "subreddit": "SideProject",
            "fetched": 2,
            "new": 2,
            "skipped": 0,
            "reddit_ids": ["a", "b"],
        }
        run_analysis_mock.return_value = {
            "filtered_out": 1,
            "analyzed": 1,
            "failed": 0,
        }

        stats = run_pipeline("need a tool", "SideProject", 10)

        run_analysis_mock.assert_called_once()
        self.assertEqual(run_analysis_mock.call_args.kwargs["reddit_ids"], ["a", "b"])
        self.assertEqual(run_analysis_mock.call_args.kwargs["source_run_id"], "run-3")
        self.assertEqual(stats["analyzed"], 1)
        self.assertEqual(stats["run_id"], "run-3")


if __name__ == "__main__":
    unittest.main()
