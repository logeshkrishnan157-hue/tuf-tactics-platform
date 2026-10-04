from flask import Flask, render_template
from dotenv import load_dotenv
import os
from app.models import db

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'tuf_tactics_secure_key_2026'
    
    # SQLite Database setup
    db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'edtech.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Register Blueprints
    from app.utils.gemini_rotator import gemini_bp
    app.register_blueprint(gemini_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    return app