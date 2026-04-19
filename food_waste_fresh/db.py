from flask import Flask
from app.config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register Blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.donor_routes import donor_bp
    from app.routes.ngo_routes import ngo_bp
    from app.routes.admin_routes import admin_bp
    from app.chatbot import chatbot_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(donor_bp)
    app.register_blueprint(ngo_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(chatbot_bp)

    return app
