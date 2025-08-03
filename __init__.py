from flask import Flask

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key' # Change this in production!

from app import routes
