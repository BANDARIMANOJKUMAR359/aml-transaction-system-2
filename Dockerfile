# Use a specific, stable Python version
FROM python:3.11-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Copy dependency files first for better caching
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create the directory structure that the Flask app expects
RUN mkdir -p app/templates app/static

# Copy the Python files into the 'app' directory
COPY __init__.py app/
COPY routes.py app/

# Copy the HTML template and CSS file into their correct subdirectories
COPY index.html app/templates/
COPY style.css app/static/

# Copy the WSGI entry point
COPY wsgi.py ./

# Expose the port the app runs on
EXPOSE 10000

# The command to run the application using a production-grade server
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "wsgi:application"]
