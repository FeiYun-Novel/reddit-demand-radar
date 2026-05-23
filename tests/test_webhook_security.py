import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from webhook.server import (
    _extract_bearer_token,
    _max_posts_per_request,
    _verify_webhook_token,
    receive_posts,
    PostPayload,
)


class WebhookSecurityTest(unittest.TestCase):
    def test_missing_webhook_token_rejects_requests(self):
        with patch.dict(os.environ, {"WEBHOOK_TOKEN": ""}):
            with self.assertRaises(HTTPException) as ctx:
                _verify_webhook_token("anything", None)

        self.assertEqual(ctx.exception.status_code, 503)

    def test_valid_header_token_is_accepted(self):
        with patch.dict(os.environ, {"WEBHOOK_TOKEN": "secret"}):
            _verify_webhook_token("secret", None)

    def test_valid_bearer_token_is_accepted(self):
        with patch.dict(os.environ, {"WEBHOOK_TOKEN": "secret"}):
            _verify_webhook_token(None, "Bearer secret")

    def test_invalid_token_is_rejected(self):
        with patch.dict(os.environ, {"WEBHOOK_TOKEN": "secret"}):
            with self.assertRaises(HTTPException) as ctx:
                _verify_webhook_token("wrong", None)

        self.assertEqual(ctx.exception.status_code, 401)

    def test_bearer_token_extraction(self):
        self.assertEqual(_extract_bearer_token("Bearer abc"), "abc")
        self.assertEqual(_extract_bearer_token("bearer abc"), "abc")
        self.assertEqual(_extract_bearer_token("Token abc"), "")

    def test_webhook_default_batch_limit_is_conservative(self):
        self.assertEqual(_max_posts_per_request(), 25)

    @patch("webhook.server.update_run")
    @patch("webhook.server.add_run_post")
    @patch("webhook.server.insert_post")
    @patch("webhook.server.create_run")
    @patch("webhook.server.init_db")
    def test_receive_posts_only_ingests_and_returns_run_id(
        self,
        init_db_mock,
        create_run_mock,
        insert_post_mock,
        add_run_post_mock,
        update_run_mock,
    ):
        create_run_mock.return_value = "run-webhook"
        insert_post_mock.return_value = True

        with patch.dict(os.environ, {"WEBHOOK_TOKEN": "secret"}):
            result = receive_posts(
                [PostPayload(title="Need a tool", reddit_id="abc", subreddit="SideProject")],
                x_webhook_token="secret",
                authorization=None,
            )

        self.assertEqual(result["run_id"], "run-webhook")
        self.assertEqual(result["analysis_status"], "not_started")
        create_run_mock.assert_called_once()
        add_run_post_mock.assert_called_once_with("run-webhook", "abc")
        update_run_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
