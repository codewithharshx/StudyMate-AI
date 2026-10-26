"""
StudyMate AI - Automated Test Suite
-----------------------------------
Verifies endpoint routing, input validation limits, safe error handling,
and provider credential protection.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

from app import app
from services import ai_service
from services.ai_service import AIServiceError, _get_client, generate_with_gemini
from werkzeug.exceptions import RequestEntityTooLarge
from io import BytesIO


class StudyMateSecurityAndValidationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_homepage_loads(self):
        """GET / should render index.html with HTTP 200."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"StudyMate", res.data)

    def test_static_assets(self):
        """Static CSS and JS should be served with HTTP 200."""
        css_res = self.client.get("/static/style.css")
        self.assertEqual(css_res.status_code, 200)
        js_res = self.client.get("/static/script.js")
        self.assertEqual(js_res.status_code, 200)

    # --- API Input Validation: /api/generate ---

    def test_generate_missing_payload(self):
        res = self.client.post("/api/generate", json=None)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()["success"])

    def test_generate_invalid_mode(self):
        res = self.client.post("/api/generate", json={"mode": "unsupported_mode", "content": "Valid study text here."})
        self.assertEqual(res.status_code, 400)
        self.assertIn("valid study mode", res.get_json()["error"])

    def test_generate_content_too_short(self):
        res = self.client.post("/api/generate", json={"mode": "summarize", "content": "short"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("little more content", res.get_json()["error"])

    def test_generate_content_too_long(self):
        res = self.client.post("/api/generate", json={"mode": "summarize", "content": "x" * 6001})
        self.assertEqual(res.status_code, 400)
        self.assertIn("too long", res.get_json()["error"])

    # --- API Input Validation: /api/quiz ---

    def test_quiz_missing_content(self):
        res = self.client.post("/api/quiz", json={"content": "", "difficulty": "medium", "num_questions": 5})
        self.assertEqual(res.status_code, 400)

    def test_quiz_invalid_difficulty(self):
        res = self.client.post("/api/quiz", json={"content": "Valid study material.", "difficulty": "extreme", "num_questions": 5})
        self.assertEqual(res.status_code, 400)
        self.assertIn("difficulty", res.get_json()["error"])

    def test_quiz_invalid_question_count(self):
        res = self.client.post("/api/quiz", json={"content": "Valid study material.", "difficulty": "medium", "num_questions": 7})
        self.assertEqual(res.status_code, 400)
        self.assertIn("5, 10, or 15", res.get_json()["error"])

    # --- API Input Validation: /api/rag/upload & /api/rag/ask ---

    def test_rag_upload_missing_file(self):
        res = self.client.post("/api/rag/upload")
        self.assertEqual(res.status_code, 400)

    def test_rag_upload_invalid_extension(self):
        data = {"file": (BytesIO(b"malicious script"), "test.exe")}
        res = self.client.post("/api/rag/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn("PDF or TXT", res.get_json()["error"])

    def test_rag_ask_empty_question(self):
        res = self.client.post("/api/rag/ask", json={"question": ""})
        self.assertEqual(res.status_code, 400)

    def test_rag_ask_question_too_long(self):
        res = self.client.post("/api/rag/ask", json={"question": "q" * 1501})
        self.assertEqual(res.status_code, 400)
        self.assertIn("1500 characters", res.get_json()["error"])

    # --- Error Handling & Payload Limits ---

    def test_file_size_limit_413_response(self):
        with app.test_request_context():
            res_tuple = app.handle_user_exception(RequestEntityTooLarge())
            response_json = res_tuple[0].get_json() if hasattr(res_tuple[0], "get_json") else res_tuple[0]
            status_code = res_tuple[1]
            self.assertEqual(status_code, 413)
            self.assertFalse(response_json["success"])
            self.assertIn("That file is too large", response_json["error"])

    # --- Provider Error Sanitization & Missing Key Behavior ---

    def test_missing_api_key_safe_behavior(self):
        """When GEMINI_API_KEY is unset, _get_client must fail safely without leaking."""
        ai_service._client = None
        with patch.dict(os.environ, {}, clear=True), \
             patch("services.ai_service.load_dotenv"):
            with self.assertRaises(AIServiceError) as ctx:
                _get_client()
            self.assertIn("Gemini API is not configured", str(ctx.exception))

    def test_api_service_sanitizes_provider_exceptions(self):
        """Provider exceptions must be caught and converted to friendly messages without raw provider dumps."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("Simulated provider connection reset")

        with patch("services.ai_service._get_client", return_value=mock_client):
            with self.assertRaises(AIServiceError) as ctx:
                generate_with_gemini("test prompt", "test instruction")
            # Must not re-raise raw unhandled provider exception
            self.assertIn("Could not connect to Gemini", str(ctx.exception))

    def test_no_secret_leakage_in_responses(self):
        """Ensure no response body or headers leak environment variable names or values."""
        res = self.client.post("/api/generate", json={})
        res_text = res.get_data(as_text=True)
        self.assertNotIn("GEMINI_API_KEY", res_text)
        self.assertNotIn("AIza", res_text)
        self.assertNotIn("AQ.", res_text)


if __name__ == "__main__":
    unittest.main()
