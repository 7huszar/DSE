FROM python:3.9-slim
WORKDIR /app

RUN pip install "fastapi[standard]" uvicorn httpx

COPY passenger.py .
EXPOSE 80

CMD ["uvicorn", "passenger:app", "--host", "0.0.0.0", "--port", "80"]