# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /LocationTracker

# Copy the application code
COPY LocationTracker.py /LocationTracker

# Install dependencies
RUN pip install flask
RUN pip install pika
RUN pip install psycopg2-binary

# Expose the application port
EXPOSE 5000

# Run the application
CMD ["python", "LocationTracker.py"]
