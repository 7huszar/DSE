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

RABBITMQ_USER = os.environ.get('RABBITMQ_USER', 'guest')
RABBITMQ_PASSWORD = os.environ.get('RABBITMQ_PASSWORD', 'guest')
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))

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
    username=RABBITMQ_USER,
    password=RABBITMQ_PASSWORD
)

def get_rabbitmq_connection():
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
    )

def establish_connection():
    global connection
    not_succeeded = True
    if connection is not None:
        if not connection.is_closed:
            return

    while not_succeeded:
        try:
            connection = get_rabbitmq_connection()
            not_succeeded = False
        except AMQPConnectionError as e:
            logger.warning(f"Failed to establish connection due to error: {repr(e)}.\n Retrying in {RETRY_WAIT} seconds.")
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
            channel.exchange_declare(exchange='broker', exchange_type='topic', durable=True)
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
        with connection_dead:
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
            with connection_dead:
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

                channel.basic_publish(
                    exchange='broker',
                    routing_key='backend.location.passenger',
                    body=json.dumps(pkg).encode("utf-8")
                )
            except (AMQPChannelError, AMQPConnectionError) as e:
                logger.warning(f"Failed to resend msg: {repr(e)}")
                with connection_dead:
                    connection_dead.notify_all()
                retry_queue.put(pkg)
                break

# Initialize connection
establish_connection()
open_channel()

@app.route('/data', methods=['POST'])
def receive_data():
    global channel
    global connection_dead

    try:
        data = request.get_json()
        logger.info(f"Received data: {str(data)}")

        # Calculate speed if we have distance data
        if 'distance_front' in data and 'distance_back' in data:
            # Estimate speed based on distance sensor data
            # This is a simplified calculation
            speed = 0
            if 'speed' not in data:
                # If DataMock doesn't send speed, calculate from other data
                # For now, use a default or calculate from position changes
                speed = 10  # Default speed in km/h
                data['speed'] = speed

        # Ensure all required fields are present
        enhanced_data = {
            'vin': data.get('vin'),
            'lat': data.get('lat'),
            'long': data.get('long'),
            'time': data.get('time'),
            'speed': data.get('speed', 0),
            'distance_front': data.get('distance_front'),
            'distance_back': data.get('distance_back')
        }

        try:
            # Send to Location Tracker
            channel.basic_publish(
                exchange='broker',
                routing_key='backend.location.tracker',
                body=json.dumps(enhanced_data).encode("utf-8")
            )

            # Send to Passenger (for frontend display)
            channel.basic_publish(
                exchange='broker',
                routing_key='backend.location.passenger',
                body=json.dumps(enhanced_data).encode("utf-8")
            )

            logger.info(f"Successfully published data for vehicle {enhanced_data['vin']}")

        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.warning(f"Failed to send message to broker: {repr(e)}")
            retry_queue.put(enhanced_data)
            with connection_dead:
                connection_dead.notify_all()

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    global connection, channel

    health_status = {
        "status": "healthy",
        "rabbitmq_connected": connection and not connection.is_closed if connection else False,
        "channel_open": channel and channel.is_open if channel else False
    }

    return jsonify(health_status), 200

if __name__ == '__main__':
    # Start background threads
    threading.Thread(target=process_failed_msg, daemon=True).start()
    threading.Thread(target=reestablish_connection, daemon=True).start()

    logger.info("Starting Location Sender service...")
    app.run(host='0.0.0.0', port=5000)