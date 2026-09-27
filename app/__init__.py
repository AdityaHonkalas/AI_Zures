import os
from flask import Flask
from dotenv import load_dotenv


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__, template_folder="templates")
    app.secret_key = os.environ.get("SECRET_KEY", "local-dev-secret")

    from app.routes import bp
    app.register_blueprint(bp)

    return app
