# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the application code
COPY consumer.py /app

# Install dependencies
RUN pip install flask
RUN pip install pika

# Run the application
CMD ["python", "consumer.py"]
