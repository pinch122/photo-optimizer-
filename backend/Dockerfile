FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (curl for health checks, libpq-dev for Postgres connection compilation if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create storage directory inside container
RUN mkdir -p /storage/original /storage/thumbnail /storage/logs

# Copy application files
COPY . .

# Expose backend port
EXPOSE 8000

# Set Python path to ensure module imports function correctly
ENV PYTHONPATH=/app

# Start application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
