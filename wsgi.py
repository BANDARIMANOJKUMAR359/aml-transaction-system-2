import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import directly from the app directory
from app import create_app
application = create_app()

if __name__ == '__main__':
    from waitress import serve
    print('Starting server on port 10000...')
    serve(application, host='0.0.0.0', port=10000)
