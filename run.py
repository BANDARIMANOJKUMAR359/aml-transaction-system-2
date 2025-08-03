import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from waitress import serve

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
