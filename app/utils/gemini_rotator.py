import os
import json
import google.generativeai as genai
from flask import Blueprint, jsonify, request
from app.models import db, QuestionCache

gemini_bp = Blueprint('gemini_bp', __name__)

def call_gemini_working_key(prompt):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        genai.configure(api_key=api_key)
        
        # Using the exact recommended model gemini-3.8-flash
        model = genai.GenerativeModel('gemini-3.8-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error with 3.8-flash: {e}")
        try:
            # Fallback to general flash variant if needed
            model = genai.GenerativeModel('gemini-flash')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e2:
            print(f"Fallback Error: {e2}")
            return None

@gemini_bp.route('/generate-unique-questions', methods=['POST'])
def generate_unique_questions():
    data = request.json
    topic = data.get('topic', 'General Programming')
    count = int(data.get('count', 10))

    existing = QuestionCache.query.filter_by(topic=topic).all()
    existing_texts = [q.question_text for q in existing]

    prompt = f"""
    Generate {count} unique multiple-choice interview questions for the topic: {topic}.
    Ensure these questions are completely distinct from these already asked questions: {existing_texts[-30:]}
    Return strictly as a JSON list of objects with keys: "question", "options" (list of 4 options), "answer", "explanation". No markdown formatting outside json if possible, just raw JSON.
    """

    raw_response = call_gemini_working_key(prompt)
    if not raw_response:
        return jsonify({"error": "API key failed to generate response!"}), 500

    try:
        cleaned_json = raw_response.replace("```json", "").replace("```", "").strip()
        questions_list = json.loads(cleaned_json)

        new_saved_questions = []
        for q in questions_list:
            q_text = q.get('question')
            if not QuestionCache.query.filter_by(question_text=q_text).first():
                opts = q.get('options', ["A", "B", "C", "D"])
                new_q = QuestionCache(
                    topic=topic,
                    question_text=q_text,
                    option_a=opts[0] if len(opts) > 0 else "",
                    option_b=opts[1] if len(opts) > 1 else "",
                    option_c=opts[2] if len(opts) > 2 else "",
                    option_d=opts[3] if len(opts) > 3 else "",
                    correct_answer=q.get('answer'),
                    explanation=q.get('explanation')
                )
                db.session.add(new_q)
                new_saved_questions.append(q)

        db.session.commit()
        return jsonify({"status": "success", "new_questions": new_saved_questions})
    
    except Exception as e:
        return jsonify({"error": str(e), "raw": raw_response}), 400

@gemini_bp.route('/test-ai')
def test_ai():
    prompt = "Give a 1-sentence welcoming quote for a smart EdTech platform students."
    ai_output = call_gemini_working_key(prompt)
    return jsonify({"response": ai_output})