# Dockerfile
FROM python:3.10-slim
RUN apt-get update -y

WORKDIR /app

COPY . /app

RUN pip install -r requirements.txt

# Expose port 8080
EXPOSE 8080

ENTRYPOINT ["python"]
CMD ["app.py"]
# End of Dockerfile