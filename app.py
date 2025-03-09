import logging
from flask import Flask
from flask_cors import CORS
from config import Config
from routes.chatbot_routes import chatbot_bp

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize CORS
    CORS(app)

    # Register blueprints
    app.register_blueprint(chatbot_bp, url_prefix="/chatbot")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)