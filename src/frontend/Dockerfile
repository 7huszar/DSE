FROM python:3.12-slim

COPY . /app
WORKDIR /app

RUN pip install pipreqs

RUN pipreqs . --force --mode no-pin

RUN pip install -r requirements.txt

EXPOSE 80

CMD ["python", "app.py"]