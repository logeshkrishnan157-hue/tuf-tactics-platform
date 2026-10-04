import os
from flask import Blueprint, jsonify, render_template, request
from app.models import db, QuestionCache

# Blueprint definition
quiz_bp = Blueprint('quiz_bp', __name__)

@quiz_bp.route('/')
def index():
    return render_template('index.html')

@quiz_bp.route('/api/get-local-quiz', methods=['GET'])
def get_local_quiz():
    topic = request.args.get('topic', 'Accounts Executive')
    # Fetch questions from local database
    questions = QuestionCache.query.filter_by(topic=topic).limit(20).all()
    
    if not questions:
        questions = QuestionCache.query.limit(20).all()

    quiz_list = []
    for q in questions:
        quiz_list.append({
            "id": q.id,
            "question": q.question_text,
            "options": [q.option_a, q.option_b, q.option_c, q.option_d],
            "answer": q.correct_answer,
            "explanation": q.explanation
        })
        
    return jsonify({"status": "success", "questions": quiz_list})