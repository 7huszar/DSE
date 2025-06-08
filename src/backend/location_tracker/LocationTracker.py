import threading
import time

import pika
import json
import os
from flask import Flask, request
import psycopg2 as psy
import logging

### CONSTANTS START ###

RETRY_WAIT = 5

### CONSTANTS END ###

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

conn = None

not_succeeded = True
while not_succeeded:
    try:
        conn = psy.connect(host=os.environ["LT_POSTGRES_HOST"], database="lt_db", user=os.environ["LT_POSTGRES_USER"], password=os.environ["LT_POSTGRES_PASSWORD"])
        not_succeeded = False
    except psy.OperationalError as e:
        logger.warning(f"Failed to connect to postgres: {repr(e)}")
    if not_succeeded:
        time.sleep(5)



app = Flask(__name__)
logger.info("Location Tracker initialized.")


def callback(ch, method, properties, body):
    # Upon receiving a message from the cars location sender, store it into the database
    information = json.loads(body.decode('UTF-8'))
    logger.info(information)
    cur = conn.cursor()
    cur.execute("INSERT INTO vehicle_positions (vin, time, longitude, latitude) VALUES (%s, %s, %s, %s)",
                (information['vin'], information['time'], information['lon'], information['lat']))
    conn.commit()

    logger.info('Message written to the db!')

def run_consumer():
    #Run the rabbitMQ Consumer that consumes the location messages
    credentials = pika.PlainCredentials(username= os.environ['RABBITMQ_USER'], password=os.environ['RABBITMQ_PASSWORD'])
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.environ['RABBITMQ_HOST'], port=os.environ['RABBITMQ_PORT'], credentials=credentials, virtual_host="/"))

    channel = connection.channel()
    logger.info("Started consumer with connection to RabbitMQ!")
    channel.exchange_declare(exchange='broker', exchange_type='topic', durable=True)
    result = channel.queue_declare('location_tracker_queue', exclusive=False)
    queue_name = result.method.queue

    channel.queue_bind(exchange='broker', queue=queue_name, routing_key='backend.location.tracker')

    channel.basic_consume(
        queue=queue_name, on_message_callback=callback, auto_ack=True)



    logger.info("RabbitMQ initialization for worker " +  threading.current_thread().name + " finished!")

    ## Postgres Initialization

    cur = conn.cursor()
    cur.execute("""DROP TABLE IF EXISTS vehicle_positions""")
    cur.execute("""
                CREATE TABLE IF NOT EXISTS vehicle_positions (
                                                                 id SERIAL PRIMARY KEY,
                                                                 vin VARCHAR(100) NOT NULL,
                    time BIGINT NOT NULL,
                    latitude FLOAT NOT NULL,
                    longitude FLOAT NOT NULL
                    )
                """)

    conn.commit()

    logger.info("PostgreSQL initialization for worker " +  threading.current_thread().name + " finished!")

    channel.start_consuming()


@app.route('/database')
def check_db_status():
    limit = request.args.get("limit", type=int)
    vin = request.args.get("vin")
    start = request.args.get("start", type=int)
    end = request.args.get("end", type=int)

    query = "SELECT * FROM vehicle_positions"
    conditions = []
    params = []

    if vin:
        conditions.append("vin = %s")
        params.append(vin)

    if start is not None and end is not None:
        conditions.append("time BETWEEN %s AND %s")
        params.append(start)
        params.append(end)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY time DESC"

    if limit:
        query += " LIMIT %s"
        params.append(limit)

    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()

    logger.info("Selected the following roles from the database:" + rows)

    return json.dumps(rows).encode('UTF-8')

if __name__ == '__main__':
    consumer_thread = threading.Thread(target=run_consumer, daemon=True)
    consumer_thread.start()

    app.run(host='0.0.0.0', port=5000)