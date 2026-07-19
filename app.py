import os

from flask import Flask

from extensions import db
from routes import register_routes
from services import initialize_database


def create_app():
    app = Flask(__name__)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///" + os.path.join(app.instance_path, "project.db").replace("\\", "/")
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")

    db.init_app(app)

    import models  

    register_routes(app)

    with app.app_context():
        initialize_database()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)