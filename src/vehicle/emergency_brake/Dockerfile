FROM python:3.9-slim

COPY /src/vehicle/emergency_brake/EmergencyBrake.py .
COPY /src/vehicle/base_rabbitmq_connection.py ./src/vehicle/
RUN pip install pika flask requests
EXPOSE 5000
CMD ["python", "EmergencyBrake.py"]