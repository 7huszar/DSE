FROM python:3.12-slim

WORKDIR /app
COPY app.py rabbitmq_bridge.py ./
COPY base_rabbitmq_connection.py ./src/vehicle/

RUN pip install pipreqs

RUN pipreqs . --force --mode no-pin

RUN pip install -r requirements.txt

EXPOSE 8080

CMD ["python", "app.py"]