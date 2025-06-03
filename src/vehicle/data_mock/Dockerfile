# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /DataMock

# Copy the application code
COPY ./src/vehicle/data_mock/DataMock.py .
COPY ./src/vehicle/data_mock/vehicle.py .
COPY ./scenarios/ ./scenarios/
COPY vehicles.json .

RUN pip install pipreqs

RUN pipreqs . --force --mode no-pin

RUN pip install -r requirements.txt

# Expose the application port
EXPOSE 5000

# Run the application
CMD ["python", "DataMock.py"]
