# Dockerfile
FROM python:3.10-slim
RUN apt-get update -y
RUN apt-get install -y python3-pip python-dev build-essential

WORKDIR /app

COPY . /app

ENV PYTHONUNBUFFERED=1 \
    GOOGLE_APPLICATION_CREDENTIALS=key.json \
    GCP_PROJECT="make-smthng-website"

RUN pip install -r requirements.txt

# Expose port 8080
EXPOSE 8080

ENTRYPOINT ["python"]
CMD ["app.py"]
# End of Dockerfile