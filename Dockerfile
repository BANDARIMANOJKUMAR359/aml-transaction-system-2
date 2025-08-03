# Use a specific, stable Python version
FROM python:3.11-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt setup.py ./

# Install dependencies
# Using setup.py makes the app package installable
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir .

# Copy the application code into the container
# The 'uploads' directory is created by the app at runtime, so it's not copied here.
COPY app ./app
COPY run.py wsgi.py ./

# Expose the port the app runs on
EXPOSE 10000

# The command to run the application using a production-grade server
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "wsgi:application"]
