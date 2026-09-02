# Dockerfile
FROM docker.io/library/python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

RUN addgroup --system app && adduser --system --ingroup app app && \
    chown -R app:app /app

USER app

# Cloud Run exposes PORT automatically
EXPOSE 8080

# Production server
CMD ["gunicorn", "--workers", "2", "--timeout", "30", "-b", "0.0.0.0:8080", "app:app"]
# End of Dockerfile
