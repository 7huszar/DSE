FROM python:3.9-slim
WORKDIR /app
COPY EmergencyBrake.py .
COPY /src/vehicle/base_rabbitmq_connection.py ./src/vehicle/
RUN pip install pika flask
EXPOSE 5000
CMD ["python", "LocationSender.py"]