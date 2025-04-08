# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /LocationSender

# Copy the application code
COPY LocationSender.py /LocationSender

# Install dependencies
RUN pip install pika

# Expose the application port
EXPOSE 5000

# Run the application
CMD ["python", "LocationSender.py"]
