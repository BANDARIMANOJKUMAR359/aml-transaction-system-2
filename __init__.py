import os
from flask import Flask

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        # A default secret that should be overridden with a random value
        SECRET_KEY='dev',
    )

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from . import routes
    app.register_blueprint(routes.main)

    return app
