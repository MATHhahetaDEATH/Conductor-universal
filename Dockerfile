# Use official python 3.11-slim as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry

# Copy poetry files
COPY pyproject.toml poetry.lock* README.md ./

# Configure poetry to not create virtualenv inside container
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

# Copy source code
COPY conductor/ ./conductor/

# Expose Flask port
EXPOSE 5678

# Set dynamic environment variables
ENV FLASK_APP=conductor.interface.api.app
ENV FLASK_RUN_HOST=0.0.0.0

# Start Flask app (placeholder for future app.py)
CMD ["flask", "run"]
