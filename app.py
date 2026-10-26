"""
StudyMate AI - Flask Backend
-----------------------------
Serves the frontend and exposes a single API endpoint (/api/generate)
that receives student content + a study mode, builds a prompt, and
calls the AI service to get an LLM-generated response.
"""

import os

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify

load_dotenv()
from services.ai_service import generate_ai_response, AIServiceError
from services.quiz_service import generate_quiz, QuizServiceError
from services.rag_service import RAGServiceError, ask_question, process_upload

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")) * 1024 * 1024

# Valid study modes supported by the app
VALID_MODES = {"summarize", "explain", "improve"}

# Input length limits
MIN_INPUT_LENGTH = 10
MAX_INPUT_LENGTH = 6000
VALID_QUIZ_COUNTS = {5, 10, 15}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    """
    Main API endpoint.

    Expects JSON:
        { "mode": "summarize" | "explain" | "improve", "content": "<text>" }

    Returns JSON:
        { "success": true, "response": "<ai text>" }
        or
        { "success": false, "error": "<friendly message>" }
    """
    # 1. Make sure we actually received JSON
    data = request.get_json(silent=True)
    if not data:
        return jsonify(success=False, error="Invalid request format."), 400

    mode = (data.get("mode") or "").strip().lower()
    content = (data.get("content") or "").strip()

    # 2. Validate mode
    if mode not in VALID_MODES:
        return jsonify(success=False, error="Please select a valid study mode."), 400

    # 3. Validate content - empty
    if not content:
        return jsonify(success=False, error="Please enter some content first."), 400

    # 4. Validate content - too short
    if len(content) < MIN_INPUT_LENGTH:
        return jsonify(success=False, error="Please provide a little more content."), 400

    # 5. Validate content - too long
    if len(content) > MAX_INPUT_LENGTH:
        return jsonify(
            success=False,
            error=f"Your input is too long. Please limit it to {MAX_INPUT_LENGTH} characters.",
        ), 400

    # 6. Call the AI service
    try:
        ai_response = generate_ai_response(mode, content)
        return jsonify(success=True, response=ai_response)
    except AIServiceError as e:
        # Known, friendly error raised by our AI service layer
        return jsonify(success=False, error=str(e)), 502
    except Exception:
        # Catch-all so we never leak a stack trace to the client
        return jsonify(
            success=False,
            error="Something went wrong on our end. Please try again.",
        ), 500


@app.route("/api/quiz", methods=["POST"])
def quiz():
    """Create a validated multiple-choice quiz from study notes."""
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    difficulty = (data.get("difficulty") or "").strip().lower()
    num_questions = data.get("num_questions")

    if not content:
        return jsonify(success=False, error="Please enter study notes first."), 400
    if len(content) < MIN_INPUT_LENGTH:
        return jsonify(success=False, error="Please provide a little more study material."), 400
    if len(content) > MAX_INPUT_LENGTH:
        return jsonify(success=False, error=f"Your input is too long. Please limit it to {MAX_INPUT_LENGTH} characters."), 400
    if difficulty not in VALID_DIFFICULTIES:
        return jsonify(success=False, error="Please select Easy, Medium, or Hard difficulty."), 400
    # bool is an int in Python, so explicitly reject it.
    if isinstance(num_questions, bool) or num_questions not in VALID_QUIZ_COUNTS:
        return jsonify(success=False, error="Please choose 5, 10, or 15 questions."), 400
    try:
        return jsonify(success=True, quiz=generate_quiz(content, num_questions, difficulty))
    except (QuizServiceError, AIServiceError) as exc:
        return jsonify(success=False, error=str(exc)), 502
    except Exception:
        return jsonify(success=False, error="Something went wrong while creating the quiz. Please try again."), 500


@app.route("/api/rag/upload", methods=["POST"])
def rag_upload():
    """Process one PDF or text study file into the in-memory FAISS store."""
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify(success=False, error="Please choose a PDF or TXT study file."), 400
    try:
        result = process_upload(uploaded_file)
        return jsonify(success=True, message="Study material uploaded successfully.", **result)
    except RAGServiceError as exc:
        return jsonify(success=False, error=str(exc)), 400
    except AIServiceError as exc:
        return jsonify(success=False, error=str(exc)), 502
    except Exception:
        return jsonify(success=False, error="The study material could not be processed. Please try again."), 500


@app.route("/api/rag/ask", methods=["POST"])
def rag_ask():
    """Answer a question using only retrieved uploaded study material."""
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify(success=False, error="Please enter a question."), 400
    if len(question) > 1500:
        return jsonify(success=False, error="Please keep your question under 1500 characters."), 400
    try:
        return jsonify(success=True, **ask_question(question))
    except RAGServiceError as exc:
        return jsonify(success=False, error=str(exc)), 400
    except AIServiceError as exc:
        return jsonify(success=False, error=str(exc)), 502
    except Exception:
        return jsonify(success=False, error="Something went wrong while answering your question. Please try again."), 500


@app.errorhandler(413)
def file_too_large(_error):
    max_mb = os.getenv("MAX_UPLOAD_SIZE_MB", "10")
    return jsonify(success=False, error=f"That file is too large. Please upload a file smaller than {max_mb} MB."), 413


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    app.run(debug=debug_mode, use_reloader=False, port=5000)
