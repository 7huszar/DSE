# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /DataMock

# Copy the application code
COPY DataMock.py.py /DataMock
COPY Vehicle.py /DataMock

# Install dependencies
RUN pip install flask

# Expose the application port
EXPOSE 5000

# Run the application
CMD ["python", "DataMock.py"]
