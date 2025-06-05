FROM python:3.9-slim

COPY /src/vehicle/emergency_brake/EmergencyBrake.py .
COPY /src/vehicle/base_rabbitmq_connection.py ./src/vehicle/

RUN pip install pipreqs

RUN pipreqs . --force --mode no-pin

RUN pip install -r requirements.txt

EXPOSE 5000
CMD ["python", "EmergencyBrake.py"]