# Dockerfile
FROM python:3.10-slim
RUN apt-get update -y

WORKDIR /app

COPY . /app

ENV PYTHONUNBUFFERED=1 \
    #GOOGLE_APPLICATION_CREDENTIALS=key.json \
    GCP_PROJECT="gpi-ai-1"

RUN pip install --upgrade pip
# Add a dummy argument to invalidate cache for pip install step
ARG CACHEBUST=1
RUN pip install -r requirements.txt

# Expose port 8080
EXPOSE 8080

ENTRYPOINT ["python"]
CMD ["app.py"]
# End of Dockerfile