FROM python:3.9-slim
WORKDIR /app

COPY ./src/vehicle/distance_monitor/DistanceMonitor.py .
COPY ./src/vehicle/base_sender_service.py ./src/vehicle/

RUN pip install pika flask
EXPOSE 5000
CMD ["python", "DistanceMonitor.py"]