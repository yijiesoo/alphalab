"""
WSGI entry point for production servers (Gunicorn, etc.)
"""
from flask_app.app import app

if __name__ == "__main__":
    app.run()
