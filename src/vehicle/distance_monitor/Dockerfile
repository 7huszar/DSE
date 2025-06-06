FROM python:3.9-slim
WORKDIR /app

COPY ./src/vehicle/distance_monitor/DistanceMonitor.py .
COPY ./src/vehicle/base_sender_service.py ./src/vehicle/
COPY ./src/vehicle/base_rabbitmq_connection.py ./src/vehicle/

RUN pip install pipreqs

RUN pipreqs . --force --mode no-pin

RUN pip install -r requirements.txt

EXPOSE 5000
CMD ["python", "DistanceMonitor.py"]