from flask import Flask
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Load config
    app.config.from_pyfile('core/config.py')

    # Register blueprints/routes
    from app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    return app
