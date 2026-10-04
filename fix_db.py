import os
from run import app, db, QuestionCache, User, InterviewResult

with app.app_context():
    # 1. Backup existing questions and interview results safely
    existing_questions = QuestionCache.query.all()
    existing_results = InterviewResult.query.all()
    print(f"Backed up {len(existing_questions)} questions and {len(existing_results)} interview results safely!")

    # 2. Recreate tables with correct columns (including percentage in InterviewResult)
    db.drop_all()
    print("Dropped old tables.")

    db.create_all()
    print("Recreated all tables with correct schema (Users + QuestionCache + InterviewResult).")

    # 3. Restore backup questions back into database
    for q in existing_questions:
        new_q = QuestionCache(
            topic=q.topic,
            question_text=q.question_text,
            option_a=q.option_a,
            option_b=q.option_b,
            option_c=q.option_c,
            option_d=q.option_d,
            correct_answer=q.correct_answer,
            explanation=q.explanation
        )
        db.session.add(new_q)

    # 4. Restore backup interview results back into database
    for r in existing_results:
        new_r = InterviewResult(
            user_id=r.user_id,
            role=r.role,
            score=r.score,
            total=r.total,
            percentage=getattr(r, 'percentage', int((r.score / r.total) * 100)),
            feedback_summary=r.feedback_summary,
            timestamp=r.timestamp
        )
        db.session.add(new_r)
    
    db.session.commit()
    print(f"Successfully restored questions and interview results back to edtech.db with percentage schema!")