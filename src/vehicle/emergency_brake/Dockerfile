FROM python:3.9-slim
WORKDIR /app
COPY EmergencyBrake.py .
RUN pip install pika
CMD ["python", "EmergencyBrake.py"]