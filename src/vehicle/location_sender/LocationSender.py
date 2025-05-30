import threading
import time

import pika
import os
import json
from flask import Flask, request, jsonify
import logging
import queue
from pika.exceptions import AMQPConnectionError, AMQPChannelError

### CONSTANTS START ###

RETRY_WAIT = 5

### CONSTANTS END ###

### DECLARATION START ###

connection = None
channel = None
logger = None
credential = None

RABBITMQ_USER = os.environ['RABBITMQ_USER']
RABBITMQ_PASSWORD = os.environ['RABBITMQ_PASSWORD']
RABBITMQ_PORT = int(os.environ['RABBIT_PORT'])

retry_queue = queue.Queue()
connection_dead = threading.Condition()

### DECLARATION END ###

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


# RabbitMQ connection
credentials = pika.PlainCredentials(
    username=os.environ['RABBITMQ_USER'],
    password=os.environ['RABBITMQ_PASSWORD']
)


def get_rabbitmq_connection():
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host='rabbitmq',
            port=RABBITMQ_PORT,
            credentials=credentials
        )
    )

def establish_connection():
    global connection
    not_succeeded = True
    while not_succeeded:
        try:
            connection = get_rabbitmq_connection()
            not_succeeded = False
        except AMQPConnectionError as e:
            logger.warning(f"Failed to establish connection due to error: {repr(e)}.\n Retrying in {RETRY_WAIT} seconds.")

        if not_succeeded:
            time.sleep(RETRY_WAIT)

    logger.info("Successfully established connection to rabbitmq.")

def open_channel():
    global channel
    global connection
    not_succeeded = True

    if connection is None or connection.is_closed:
        establish_connection()

    while not_succeeded:
        try:
            channel = connection.channel()
            not_succeeded = False
        except AMQPConnectionError as e:
            logger.warning(f"Failed to open channel: {repr(e)}")
            establish_connection()
        except AMQPChannelError as e:
            logger.warning(f"Failed to open channel: {repr(e)}")

    logger.info("Successfully opened channel of rabbitmq.")

def reestablish_connection():
    global connection
    global channel
    global connection_dead


    while True:
        connection_dead.wait()
        establish_connection()
        open_channel()

def process_failed_msg():
    global retry_queue
    global channel
    global connection
    global connection_dead

    while True:
        with retry_queue.not_empty:
            while retry_queue.empty():
                retry_queue.not_empty.wait()

        if channel.is_closed or connection.is_closed:
            connection_dead.notify_all()
            time.sleep(RETRY_WAIT)
            continue

        logger.info("Try to resend all failed msg.")

        while not retry_queue.empty():
            pkg = retry_queue.get()

            try:

                channel.basic_publish(
                    exchange='broker',
                    routing_key='backend.location.tracker',
                    body=json.dumps(pkg).encode("utf-8")
                )
            except (AMQPChannelError, AMQPConnectionError) as e:
                logger.warning(f"Failed to resend msg: {repr(e)}")
                connection_dead.notify_all()
                retry_queue.put(pkg)
                break

establish_connection()
open_channel()

connection_open = True

channel.exchange_declare(exchange='broker', exchange_type='topic', durable=True)

if channel.is_closed:
    logger.error("channel closed")
    raise Exception

@app.route('/data', methods=['POST'])
def receive_data():
    global channel
    global connection_dead
    data = request.get_json()
    logger.info(f"Received data: {str(data)}")

    try:
        channel.basic_publish(
            exchange='broker',
            routing_key='backend.location.tracker',
            body=json.dumps(data).encode("utf-8")
        )

    except AMQPConnectionError as e:
        logger.warning(f"Failed to send message to broker with routing key: 'backend.location.tracker' because of connection error: {repr(e)}")
        retry_queue.put(data)
        connection_dead.notify_all()
    except AMQPChannelError as e:
        logger.warning(f"Failed to send message to broker with routing key: 'backend.location.tracker' because of channel error: {repr(e)}")
        retry_queue.put(data)
        connection_dead.notify_all()


    try:
        channel.basic_publish(
            exchange='broker',
            routing_key='backend.location.passenger',
            body=json.dumps(data).encode("utf-8")
        )

    except AMQPConnectionError as e:
        logger.warning(f"Failed to send message to broker with routing key: 'backend.location.passenger' because of connection error: {repr(e)}")
        retry_queue.put(data)
        connection_dead.notify_all()
    except AMQPChannelError as e:
        logger.warning(f"Failed to send message to broker with routing key: 'backend.location.passenger' because of channel error: {repr(e)}")
        retry_queue.put(data)
        connection_dead.notify_all()

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    # Start Flask app
    app.run(host='0.0.0.0', port=5000)