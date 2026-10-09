import asyncio
import unittest
from unittest import mock

import requests

import server


class ChatBackendErrorsTests(unittest.TestCase):
    def test_chat_backend_hint_is_actionable(self):
        message = server._chat_backend_hint(error=RuntimeError("connection refused"))
        self.assertIn("Chat model unavailable", message)
        self.assertIn("CHAT_URL", message)
        self.assertIn("Start the local model server", message)

    def test_model_status_reports_guidance_when_backend_is_down(self):
        with mock.patch.object(server.requests, "get", side_effect=requests.ConnectionError("connection refused")):
            status = asyncio.run(server.model_status())
        self.assertFalse(status["available"])
        self.assertIn("Chat model unavailable", status["status"])
        self.assertIn("Start your local model server", status["help"])


if __name__ == "__main__":
    unittest.main()
