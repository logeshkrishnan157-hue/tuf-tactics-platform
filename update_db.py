import sqlite3
import os

db_path = os.path.abspath("edtech.db")
print("Updating database at:", db_path)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # 1. Add category column to question_cache if not exists (Preserves existing questions safely!)
    cursor.execute("PRAGMA table_info(question_cache);")
    columns = [col[1] for col in cursor.fetchall()]
    if 'category' not in columns:
        cursor.execute("ALTER TABLE question_cache ADD COLUMN category VARCHAR(150);")
        print("Successfully added 'category' to 'question_cache'!")

    # 2. Safely check and update active_interviews table without dropping data
    cursor.execute("CREATE TABLE IF NOT EXISTS active_interviews (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id VARCHAR(20) UNIQUE NOT NULL, role VARCHAR(100) NOT NULL, questions TEXT NOT NULL, current_index INTEGER DEFAULT 0, user_answers TEXT DEFAULT '{}');")
    cursor.execute("PRAGMA table_info(active_interviews);")
    ai_columns = [col[1] for col in cursor.fetchall()]
    
    if 'current_round' not in ai_columns:
        cursor.execute("ALTER TABLE active_interviews ADD COLUMN current_round INTEGER DEFAULT 1;")
        print("Successfully added 'current_round' to 'active_interviews'!")
    if 'round_scores' not in ai_columns:
        cursor.execute("ALTER TABLE active_interviews ADD COLUMN round_scores TEXT DEFAULT '{}';")
        print("Successfully added 'round_scores' to 'active_interviews'!")

    # 3. Create active_quizzes table if not exists for Mock Test persistent state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(20) UNIQUE NOT NULL,
            persona VARCHAR(100) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            questions TEXT NOT NULL,
            current_index INTEGER DEFAULT 0,
            user_answers TEXT DEFAULT '{}'
        );
    """)

    conn.commit()
    print("Database updated successfully! All your cached questions are fully preserved.")

except Exception as e:
    print("Error updating database:", e)

conn.close()