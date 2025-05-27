FROM python:3.9-slim
WORKDIR /app
COPY EmergencyBrake.py .
RUN pip install pika flask
EXPOSE 5000
CMD ["python", "LocationSender.py"]