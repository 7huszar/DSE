FROM python:3.9-slim
WORKDIR /app
COPY CentralDirector.py .
RUN pip install pika psycopg2-binary flask requests
CMD ["python", "CentralDirector.py"]