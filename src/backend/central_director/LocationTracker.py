import threading
import pika
import json
import os
from flask import Flask
import psycopg2 as psy
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


conn = psy.connect(host=os.environ["CD_POSTGRES_HOST"], database="cd_db", user=os.environ["CD_POSTGRES_USER"], password=os.environ["CD_POSTGRES_PASSWORD"])



app = Flask(__name__)
logger.info("Location Tracker initialized.")


def callback(ch, method, properties, body):

    information = json.loads(body.decode('UTF-8'))
    logger.info(information)
    cur = conn.cursor()
    cur.execute("INSERT INTO vehicle_positions (vin, time, longitude, latitude) VALUES (%s, %s, %s, %s)",
                (information['vin'], information['time'], information['long'], information['lat']))
    conn.commit()

    logger.info('Message written to the db!')

def run_consumer():
    ##RabbitMQ initialization
    credentials = pika.PlainCredentials(username= os.environ['RABBITMQ_USER'], password=os.environ['RABBITMQ_PASSWORD'])
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.environ['RABBITMQ_HOST'], port=os.environ['RABBITMQ_PORT'], credentials=credentials, virtual_host="/"))

    channel = connection.channel()
    logger.info("Started consumer with connection to RabbitMQ!")
    channel.exchange_declare(exchange='broker', exchange_type='topic')
    result = channel.queue_declare('', exclusive=False)
    queue_name = result.method.queue

    channel.queue_bind(exchange='broker', queue=queue_name, routing_key='backend.central')

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

@app.route('/messages')
def check_status():
    global msg
    global received_cnt

    payload = {
        'key' : msg,
        'cnt' : received_cnt
    }
    return json.dumps(payload).encode('UTF-8')


@app.route('/database')
def check_db_status():
    cur = conn.cursor()
    cur.execute("SELECT * FROM vehicle_positions")
    rows = cur.fetchall()
    logger.info(rows)

    return json.dumps(rows).encode('UTF-8')

if __name__ == '__main__':
    consumer_thread = threading.Thread(target=run_consumer, daemon=True)
    consumer_thread.start()

    app.run(host='0.0.0.0', port=5000)