FROM python:3.9-slim
WORKDIR /app
COPY BackendDistanceMonitor.py .
RUN pip install pika requests
CMD ["python", "BackendDistanceMonitor.py"]