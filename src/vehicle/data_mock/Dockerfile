# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /DataMock

# Copy the application code
COPY ./src/vehicle/data_mock/DataMock.py .
COPY ./src/vehicle/data_mock/vehicle.py .
COPY vehicles.json .

# Install dependencies
RUN pip install flask requests
RUN pip install numpy

# Expose the application port
EXPOSE 5000

# Run the application
CMD ["python", "DataMock.py"]
