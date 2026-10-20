import os

from flask import Flask
from werkzeug.security import generate_password_hash

from models import User, db

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def seed_admin():
    """Create the single pre-existing admin if absent. Credentials come from env vars."""
    if User.query.filter_by(role="admin").first():
        return
    db.session.add(
        User(
            name="Admin",
            email=os.environ.get("TMA_ADMIN_EMAIL", "admin@tma.local"),
            password_hash=generate_password_hash(os.environ.get("TMA_ADMIN_PASSWORD", "admin123")),
            role="admin",
        )
    )
    db.session.commit()


def create_app(db_uri=None):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri or "sqlite:///" + os.path.join(BASE_DIR, "tma.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        seed_admin()
    return app


if __name__ == "__main__":
    create_app()
    print("Database created and admin seeded.")
