from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'super-secret-key'

    with app.app_context():
        from . import routes

    return app
