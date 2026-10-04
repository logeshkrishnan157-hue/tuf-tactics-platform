import os
import csv
import random
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import google.generativeai as genai
import pypdf
import docx

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'app', 'templates')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'uploads')

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'edtech.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'tuftactics_secret_secure_key'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMPLATE_DIR, exist_ok=True)

db = SQLAlchemy(app)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    user_unique_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(10), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    pin = db.Column(db.String(4), nullable=False)

class InterviewResult(db.Model):
    __tablename__ = 'interview_results'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    percentage = db.Column(db.Integer, nullable=False)
    feedback_summary = db.Column(db.Text, nullable=False)
    review_details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)

class QuestionCache(db.Model):
    __tablename__ = 'question_cache'
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(150), index=True, nullable=False)
    category = db.Column(db.String(150), nullable=True)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text, nullable=False)
    answer = db.Column(db.String(255), nullable=False)
    explanation = db.Column(db.Text, nullable=True)

class ActiveInterview(db.Model):
    __tablename__ = 'active_interviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), unique=True, nullable=False)
    role = db.Column(db.String(100), nullable=False)
    questions = db.Column(db.Text, nullable=False)
    current_index = db.Column(db.Integer, default=0)
    user_answers = db.Column(db.Text, default='{}')
    current_round = db.Column(db.Integer, default=1)
    round_scores = db.Column(db.Text, default='{}')

class ActiveQuiz(db.Model):
    __tablename__ = 'active_quizzes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), unique=True, nullable=False)
    persona = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    questions = db.Column(db.Text, nullable=False)
    current_index = db.Column(db.Integer, default=0)
    user_answers = db.Column(db.Text, default='{}')

def append_to_daily_report(user_id, name, email, category, rating, message):
    csv_file = os.path.join(BASE_DIR, 'daily_report.csv')
    file_exists = os.path.isfile(csv_file)
    try:
        with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Timestamp', 'User ID', 'Name', 'Email', 'Category', 'Rating', 'Message'])
            writer.writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, name, email, category, rating, message])
    except Exception as e:
        print("CSV Log Warning:", e)

def log_new_user_to_csv(user_id, name, email, phone, age):
    csv_file = os.path.join(BASE_DIR, 'new_users_report.csv')
    file_exists = os.path.isfile(csv_file)
    try:
        with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Timestamp', 'User ID', 'Name', 'Email', 'Phone', 'Age'])
            writer.writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, name, email, phone, age])
    except Exception as e:
        print("CSV Log Warning:", e)

def extract_text_from_file(filepath):
    text = ""
    if filepath.endswith('.pdf'):
        try:
            reader = pypdf.PdfReader(filepath)
            for page in reader.pages:
                t = page.extract_text()
                if t: text += t + "\n"
        except Exception as e:
            print("PDF Error:", e)
    elif filepath.endswith('.docx'):
        try:
            doc = docx.Document(filepath)
            for para in doc.paragraphs:
                text += para.text + "\n"
        except Exception as e:
            print("DOCX Error:", e)
    return text.strip()

def is_valid_resume(text):
    lower_text = text.lower()
    resume_keywords = ['experience', 'skills', 'education', 'projects', 'summary', 'work', 'profile', 'developer', 'engineer', 'analyst', 'degree', 'resume']
    matches = sum(1 for kw in resume_keywords if kw in lower_text)
    return len(text) > 80 and matches >= 2

def get_user_asked_questions(uid):
    past_results = InterviewResult.query.filter_by(user_id=uid).all()
    asked_texts = set()
    for res in past_results:
        if res.review_details:
            try:
                details = json.loads(res.review_details)
                for item in details:
                    if 'question' in item:
                        asked_texts.add(item['question'].strip())
            except:
                pass
    return asked_texts

@app.route('/')
def index():
    theme = session.get('theme', 'dark')
    return render_template('index.html', user_name=session.get('user_name'), theme=theme)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip().lower()
        pin = request.form.get('pin', '').strip()
        user = User.query.filter((db.func.lower(User.email) == identifier) | (User.phone == identifier)).first()
        if user and user.pin == pin:
            session['user_id'] = user.user_unique_id
            session['user_name'] = user.name
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid Email/Phone or 4-Digit PIN!", is_success=False, theme=session.get('theme', 'dark'))
    return render_template('login.html', theme=session.get('theme', 'dark'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        age = request.form.get('age', 20)
        pin = request.form.get('pin', '').strip()
        
        if len(phone) != 10 or not phone.isdigit():
            return render_template('signup.html', error="Phone number must be exactly 10 numeric digits!", theme=session.get('theme', 'dark'))
        if len(pin) != 4 or not pin.isdigit():
            return render_template('signup.html', error="PIN must be exactly 4 numeric digits!", theme=session.get('theme', 'dark'))
        if User.query.filter_by(email=email).first():
            return render_template('signup.html', error="Email already registered! Please sign in.", theme=session.get('theme', 'dark'))
        
        unique_id = f"TUF-{random.randint(10000, 99999)}"
        new_user = User(user_unique_id=unique_id, name=name, email=email, phone=phone, age=int(age), pin=pin)
        db.session.add(new_user)
        db.session.commit()
        log_new_user_to_csv(unique_id, name, email, phone, age)

        session['user_id'] = unique_id
        session['user_name'] = new_user.name
        return redirect(url_for('dashboard'))
    return render_template('signup.html', theme=session.get('theme', 'dark'))

@app.route('/forgot-pin', methods=['GET', 'POST'])
def forgot_pin():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip().lower()
        name = request.form.get('name', '').strip().lower()
        new_pin = request.form.get('new_pin', '').strip()
        if len(new_pin) != 4 or not new_pin.isdigit():
            return render_template('forgot_pin.html', error="New PIN must be exactly 4 digits!", theme=session.get('theme', 'dark'))
        user = User.query.filter(((db.func.lower(User.email) == identifier) | (db.func.lower(User.phone) == identifier)) & (db.func.lower(User.name) == name)).first()
        if user:
            user.pin = new_pin
            db.session.commit()
            return render_template('login.html', error="PIN successfully updated! Please sign in with your new PIN.", is_success=True, theme=session.get('theme', 'dark'))
        else:
            return render_template('forgot_pin.html', error="Verification failed! Records do not match.", theme=session.get('theme', 'dark'))
    return render_template('forgot_pin.html', theme=session.get('theme', 'dark'))

@app.route('/update-pin', methods=['POST'])
def update_pin():
    if 'user_id' not in session: return redirect(url_for('login'))
    uid = session.get('user_id')
    user = User.query.filter_by(user_unique_id=uid).first()
    current_pin = request.form.get('current_pin', '').strip()
    new_pin = request.form.get('new_pin', '').strip()
    
    if not user or user.pin != current_pin:
        return redirect(url_for('dashboard'))
    if len(new_pin) == 4 and new_pin.isdigit():
        user.pin = new_pin
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(user_unique_id=session.get('user_id')).first()
    uid = session.get('user_id')
    
    past_records = InterviewResult.query.filter_by(user_id=uid).order_by(InterviewResult.id.desc()).all()
    
    total_tests = sum(1 for r in past_records if r.role.startswith("Mock Test:"))
    total_interviews = sum(1 for r in past_records if r.role.startswith("Interview:"))
    avg_score = int(sum([item.percentage for item in past_records]) / len(past_records)) if past_records else 0

    now = datetime.now()
    processed_records = []
    for item in past_records:
        review_data = []
        is_expired = (now - item.timestamp) > timedelta(hours=24)
        if not is_expired and item.review_details:
            try: 
                review_data = json.loads(item.review_details)
            except: 
                review_data = []
        
        processed_records.append({
            "id": item.id, 
            "role": item.role, 
            "score": item.score, 
            "total": item.total,
            "percentage": item.percentage, 
            "feedback_summary": item.feedback_summary,
            "review": review_data, 
            "is_expired": is_expired, 
            "timestamp": item.timestamp.strftime('%Y-%m-%d %H:%M') if item.timestamp else ""
        })

    return render_template(
        'dashboard.html', 
        user_name=user.name if user else session.get('user_name'), 
        user_id=uid, 
        past_interviews=processed_records, 
        avg_score=avg_score, 
        total_tests=total_tests, 
        total_interviews=total_interviews, 
        theme=session.get('theme', 'dark')
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/about')
def about():
    return render_template('about.html', theme=session.get('theme', 'dark'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    success_msg = None
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        category = request.form.get('category', 'General Feedback').strip()
        rating = int(request.form.get('rating', 5))
        msg_text = request.form.get('message', '').strip()
        if name and email and msg_text:
            append_to_daily_report(session.get('user_id', 'GUEST'), name, email, category, rating, msg_text)
            success_msg = "Thank you! Your feedback and review have been successfully recorded."
    return render_template('contact.html', success_msg=success_msg, theme=session.get('theme', 'dark'))

@app.route('/terms')
def terms():
    return render_template('terms.html', theme=session.get('theme', 'dark'))

def generate_interview_round(target_role, resume_text, round_num, asked_texts):
    q_count = 10
    model = genai.GenerativeModel('gemini-3.8-flash')
    focus = "Core Technical Concepts" if round_num == 1 else ("Advanced Architecture & Problem Solving" if round_num == 2 else "System Design, Leadership & Scenarios")
    prompt = f"Apply 80-20 rule (80% core, 20% conceptual). Generate {q_count + 5} unique questions for Round {round_num} ({focus}) for '{target_role}' based on resume. Output strictly as a JSON array with keys: 'category', 'question', 'options' (array of 4), 'answer', 'explanation'.\n\nRESUME:\n{resume_text[:2500]}"
    try:
        response = model.generate_content(prompt)
        ai_data = json.loads(response.text.strip().replace("```json", "").replace("```", "").strip())
        questions = []
        for item in ai_data:
            q_text = item.get('question')
            if q_text and q_text.strip() not in asked_texts and len(questions) < q_count:
                questions.append({
                    "id": len(questions)+1,
                    "category": f"Round {round_num}: {item.get('category', focus)}",
                    "question": q_text,
                    "options": item.get('options'),
                    "answer": item.get('answer'),
                    "explanation": item.get('explanation', "Professional expert rationale.")
                })
        return questions
    except Exception as e:
        print("AI Interview Gen Error:", e)
        return []

@app.route('/mock-interview', methods=['GET', 'POST'])
def mock_interview():
    if 'user_id' not in session: return redirect(url_for('login'))
    uid = session.get('user_id')
    
    active = ActiveInterview.query.filter_by(user_id=uid).first()
    if active:
        return redirect(url_for('interview_live'))

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    already_taken = InterviewResult.query.filter(InterviewResult.user_id == uid, InterviewResult.role.like("Interview:%"), InterviewResult.timestamp >= today_start).first()
    if already_taken:
        return render_template('mock_setup.html', error="⚠ Daily Limit Reached: You can only take 1 Mock Interview per day. Come back tomorrow!", theme=session.get('theme', 'dark'))

    if request.method == 'POST':
        target_role = request.form.get('target_role', 'Software Engineer').strip()
        resume_file = request.files.get('resume')
        
        if not resume_file or resume_file.filename == '':
            return render_template('mock_setup.html', error="⚠ Please upload a valid resume file (PDF or DOCX).", theme=session.get('theme', 'dark'))
        
        filename = secure_filename(resume_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        resume_file.save(filepath)
        resume_text = extract_text_from_file(filepath)
        if os.path.exists(filepath): os.remove(filepath)
        
        if not is_valid_resume(resume_text):
            return render_template('mock_setup.html', error="❌ Invalid Document! Uploaded file does not look like a professional resume.", theme=session.get('theme', 'dark'))

        asked_texts = get_user_asked_questions(uid)
        questions = generate_interview_round(target_role, resume_text, 1, asked_texts)
        if not questions:
            return render_template('mock_setup.html', error="⚠ AI Generation Error. Please try again.", theme=session.get('theme', 'dark'))

        active = ActiveInterview(user_id=uid, role=target_role, questions=json.dumps(questions), current_index=0, user_answers=json.dumps({}), current_round=1, round_scores=json.dumps({}))
        db.session.add(active)
        db.session.commit()

        return redirect(url_for('interview_live'))
    return render_template('mock_setup.html', theme=session.get('theme', 'dark'))

@app.route('/mock-live', methods=['GET', 'POST'])
def interview_live():
    if 'user_id' not in session: return redirect(url_for('login'))
    uid = session.get('user_id')
    active = ActiveInterview.query.filter_by(user_id=uid).first()
    if not active: return redirect(url_for('mock_interview'))

    questions = json.loads(active.questions)
    idx = active.current_index
    user_answers = json.loads(active.user_answers)

    if request.method == 'POST':
        user_answers[str(idx)] = request.form.get('answer')
        idx += 1
        active.current_index = idx
        active.user_answers = json.dumps(user_answers)
        db.session.commit()

        mistakes_count = 0
        for q_idx in range(idx):
            u_ans = user_answers.get(str(q_idx))
            if u_ans and str(u_ans).strip() != str(questions[q_idx]['answer']).strip():
                mistakes_count += 1

        if mistakes_count >= 5 or idx >= len(questions):
            score = 0
            detailed_review = []
            for q_idx in range(idx):
                q = questions[q_idx]
                u_ans = user_answers.get(str(q_idx), "Not Answered")
                is_correct = (str(u_ans).strip() == str(q['answer']).strip())
                if is_correct: score += 1
                detailed_review.append({"question": q['question'], "category": q['category'], "user_ans": u_ans, "correct_ans": q['answer'], "is_correct": is_correct, "explanation": q['explanation']})
            
            round_scores = json.loads(active.round_scores)
            round_scores[str(active.current_round)] = {"score": score, "total": idx, "review": detailed_review}
            active.round_scores = json.dumps(round_scores)
            db.session.commit()

            passed = (score >= 6) and (mistakes_count < 5)

            if passed and active.current_round < 3:
                next_round = active.current_round + 1
                active.current_round = next_round
                asked_texts = get_user_asked_questions(uid)
                new_qs = generate_interview_round(active.role, "Candidate Profile", next_round, asked_texts)
                active.questions = json.dumps(new_qs)
                active.current_index = 0
                active.user_answers = json.dumps({})
                db.session.commit()
                return redirect(url_for('interview_live'))
            else:
                all_reviews = []
                total_score = 0
                total_q = 0
                for r_num, r_data in round_scores.items():
                    total_score += r_data['score']
                    total_q += r_data['total']
                    all_reviews.extend(r_data['review'])
                
                percentage = int((total_score / total_q) * 100) if total_q > 0 else 0
                feedback_msg = f"🎉 Successfully completed all 3 Rounds!" if active.current_round == 3 and passed else f"⚠ Interview ended at Round {active.current_round} (Score: {total_score}/{total_q})."
                
                db.session.add(InterviewResult(
                    user_id=uid, role=f"Interview: {active.role}", score=total_score, total=total_q, percentage=percentage,
                    feedback_summary=feedback_msg, review_details=json.dumps(all_reviews)
                ))
                db.session.delete(active)
                db.session.commit()
                return redirect(url_for('dashboard'))

    return render_template('mock_live.html', question=questions[idx], index=idx+1, total=len(questions), role=f"{active.role} (Round {active.current_round} of 3)", theme=session.get('theme', 'dark'))

@app.route('/quiz', methods=['GET'])
def quiz():
    if 'user_id' not in session: return redirect(url_for('login'))
    uid = session.get('user_id')
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    already_taken = InterviewResult.query.filter(InterviewResult.user_id == uid, InterviewResult.role.like("Mock Test:%"), InterviewResult.timestamp >= today_start).first()
    if already_taken:
        return render_template('quiz_setup.html', error="⚠️ Daily Limit Reached: You can only take 1 Mock Test per day. Come back tomorrow!", theme=session.get('theme', 'dark'))
    return render_template('quiz_setup.html', theme=session.get('theme', 'dark'))

@app.route('/quiz-live')
def quiz_live():
    if 'user_id' not in session: return redirect(url_for('login'))
    uid = session.get('user_id')
    
    persona = request.args.get('persona', 'Student')
    subject = request.args.get('subject', 'General Assessment')
    count = int(request.args.get('count', 10))

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    already_taken = InterviewResult.query.filter(InterviewResult.user_id == uid, InterviewResult.role.like("Mock Test:%"), InterviewResult.timestamp >= today_start).first()
    if already_taken:
        return redirect(url_for('quiz'))

    return render_template('quiz.html', persona=persona, subject=subject, count=count, theme=session.get('theme', 'dark'))

@app.route('/api/get-dynamic-quiz', methods=['GET'])
def get_dynamic_quiz():
    if 'user_id' not in session: return jsonify({"status": "unauthorized"}), 401
    uid = session.get('user_id')
    persona = request.args.get('persona', 'Student')
    subject = request.args.get('subject', 'General').strip()
    count = int(request.args.get('count', 10))
    
    asked_texts = get_user_asked_questions(uid)
    cached_questions = QuestionCache.query.filter_by(topic=subject).all()
    available_cached = [q for q in cached_questions if q.question_text.strip() not in asked_texts]
    
    quiz_list = []
    if len(available_cached) >= count:
        selected_qs = random.sample(available_cached, count)
        for q in selected_qs:
            quiz_list.append({"id": len(quiz_list)+1, "topic": subject, "category": q.category if q.category else subject, "question": q.question_text, "options": json.loads(q.options), "answer": q.answer, "explanation": q.explanation})
    else:
        try:
            model = genai.GenerativeModel('gemini-3.8-flash')
            prompt = f"Apply 80-20 rule (80% core/PYQ, 20% conceptual). Generate {count} unique multiple-choice questions on '{subject}' for a '{persona}'. Output strictly JSON array with keys: 'category', 'question', 'options' (array of 4), 'answer', 'explanation'."
            response = model.generate_content(prompt)
            ai_data = json.loads(response.text.strip().replace("```json", "").replace("```", "").strip())
            
            for item in ai_data:
                q_text = item.get('question')
                opts = item.get('options', ["A", "B", "C", "D"])
                ans = item.get('answer', opts[0] if opts else "A")
                exp = item.get('explanation', "Expert rationale.")
                cat = item.get('category', subject)
                
                if q_text and q_text.strip() not in asked_texts:
                    if not QuestionCache.query.filter_by(topic=subject, question_text=q_text).first():
                        db.session.add(QuestionCache(topic=subject, category=cat, question_text=q_text, options=json.dumps(opts), answer=ans, explanation=exp))
                    quiz_list.append({"id": len(quiz_list)+1, "topic": subject, "category": cat, "question": q_text, "options": opts, "answer": ans, "explanation": exp})
            db.session.commit()
        except Exception as e:
            print("Quiz AI Gen Error:", e)

        while len(quiz_list) < count:
            idx = len(quiz_list) + 1
            quiz_list.append({
                "id": idx,
                "topic": subject,
                "category": f"{subject} Core & Conceptual",
                "question": f"Practice Question {idx} focusing on core & conceptual analysis for {subject}",
                "options": ["Option A (Standard)", "Option B", "Option C", "Option D"],
                "answer": "Option A (Standard)",
                "explanation": "Detailed analytical breakdown for professional practice."
            })

    return jsonify({"status": "success", "questions": quiz_list[:count]})

@app.route('/api/set-theme', methods=['POST'])
def set_theme():
    session['theme'] = request.get_json().get('theme', 'dark')
    return jsonify({"status": "success"})

@app.route('/api/save-quiz-result', methods=['POST'])
def save_quiz_result():
    if 'user_id' not in session: return jsonify({"status": "unauthorized"}), 401
    uid = session.get('user_id')
    data = request.get_json()
    subject = data.get('subject', 'Assessment')
    
    db.session.add(InterviewResult(
        user_id=uid, role=f"Mock Test: {subject}", score=data.get('score', 0), total=data.get('total', 10), percentage=data.get('percentage', 0),
        feedback_summary=f"Mock Test: Scored {data.get('score', 0)}/{data.get('total', 10)} ({data.get('percentage', 0)}%).", review_details=json.dumps(data.get('review', []))
    ))
    db.session.commit()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    with app.app_context():
        # Clean sync for deployment & cache preservation
        db.create_all()
    app.run(debug=True, port=5000)
