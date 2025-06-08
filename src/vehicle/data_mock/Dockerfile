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

RUN pip install "fastapi[standard]" uvicorn

# Expose the application port
EXPOSE 80

# Run the application
CMD ["uvicorn", "DataMock:app", "--host", "0.0.0.0", "--port", "80"]
