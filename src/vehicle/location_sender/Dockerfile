FROM python:3.9-slim
WORKDIR /app
COPY LocationSender.py .
RUN pip install pika flask
EXPOSE 5000
CMD ["python", "LocationSender.py"]