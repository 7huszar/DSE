FROM python:3.9-slim

WORKDIR /app

COPY CentralDirector.py .

RUN pip install pika psycopg2-binary

# Central Director doesn't need to expose a port as it only consumes messages
CMD ["python", "CentralDirector.py"]