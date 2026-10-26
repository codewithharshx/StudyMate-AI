"""Quiz prompt building, JSON parsing, and defensive quiz validation."""

import json
import re

from services.ai_service import AIServiceError, generate_with_gemini


class QuizServiceError(Exception):
    """Friendly quiz-specific error."""


def _validate_quiz(payload, requested_count):
    if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
        raise QuizServiceError("The AI response could not be processed. Please try again.")
    questions = payload["questions"]
    if len(questions) != requested_count:
        raise QuizServiceError("The AI returned an incomplete quiz. Please generate a new quiz.")
    clean_questions = []
    for item in questions:
        if not isinstance(item, dict):
            raise QuizServiceError("The AI returned an invalid quiz. Please try again.")
        question = item.get("question")
        options = item.get("options")
        correct = item.get("correct_answer")
        explanation = item.get("explanation")
        if (not isinstance(question, str) or not question.strip() or not isinstance(options, list)
                or len(options) != 4 or not all(isinstance(option, str) and option.strip() for option in options)
                or isinstance(correct, bool) or not isinstance(correct, int) or correct not in range(4)
                or not isinstance(explanation, str) or not explanation.strip()):
            raise QuizServiceError("The AI returned an invalid quiz. Please try again.")
        clean_questions.append({"question": question.strip(), "options": [option.strip() for option in options],
                                "correct_answer": correct, "explanation": explanation.strip()})
    return {"questions": clean_questions}


def generate_quiz(content, num_questions, difficulty):
    prompt = f"""Create exactly {num_questions} {difficulty}-difficulty multiple-choice questions from the study notes below.
Return ONLY a valid JSON object, with no markdown fences or extra text, using this exact shape:
{{"questions":[{{"question":"...","options":["...","...","...","..."],"correct_answer":0,"explanation":"..."}}]}}
Every question must have exactly four options, correct_answer must be an integer from 0 to 3, and explanations must be short. Base questions only on the supplied notes.

Study notes:
{content}"""
    raw = generate_with_gemini(prompt, "You create accurate student quizzes and return strictly valid JSON.", 4000, 0.2)
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise QuizServiceError("The AI response could not be processed. Please try again.") from exc
    return _validate_quiz(payload, num_questions)
