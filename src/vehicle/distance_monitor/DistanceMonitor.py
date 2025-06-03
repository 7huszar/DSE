import time
import pika
import os
import json
from flask import Flask, request, jsonify
import logging
from pika.exceptions import AMQPConnectionError
import threading

### CONSTANTS START ###
RETRY_WAIT = 5
CRITICAL_DISTANCE_FRONT = 0.5  # Critical distance in meters for front
### CONSTANTS END ###

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Global variables for tracking
last_time_stamp = 0
last_distance_front = 0
last_distance_back = 0
vehicle_vin = None
vehicle_speed = 0

# RabbitMQ connection variables
connection = None
channel = None
credentials = None

def init_rabbitmq():
    global connection, channel, credentials

    credentials = pika.PlainCredentials(
        username=os.environ.get('RABBITMQ_USER', 'guest'),
        password=os.environ.get('RABBITMQ_PASSWORD', 'guest')
    )

    not_succeeded = True
    while not_succeeded:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=os.environ.get('RABBITMQ_HOST', 'rabbitmq'),
                    port=int(os.environ.get('RABBITMQ_PORT', 5672)),
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
            )
            channel = connection.channel()
            channel.exchange_declare(exchange='broker', exchange_type='topic', durable=True)
            not_succeeded = False
            logger.info("Successfully connected to RabbitMQ")
        except AMQPConnectionError as e:
            logger.warning(f"Failed to connect to RabbitMQ: {repr(e)}. Retrying in {RETRY_WAIT} seconds.")
            time.sleep(RETRY_WAIT)

def publish_distance_data(vin, distance_front, distance_back, change_rate_front, change_rate_back):
    """Publish distance data to different topics"""
    global channel

    try:
        # Publish to Central Director
        distance_data = {
            'vin': vin,
            'distance_front': distance_front,
            'distance_back': distance_back,
            'change_rate_front': change_rate_front,
            'change_rate_back': change_rate_back,
            'timestamp': time.time()
        }

        # Send to backend.distance topics for Central Director
        channel.basic_publish(
            exchange='broker',
            routing_key='backend.distance.front',
            body=json.dumps({
                'vin': vin,
                'distance': distance_front,
                'change_rate': change_rate_front
            }).encode('utf-8')
        )

        channel.basic_publish(
            exchange='broker',
            routing_key='backend.distance.back',
            body=json.dumps({
                'vin': vin,
                'distance': distance_back,
                'change_rate': change_rate_back
            }).encode('utf-8')
        )

        # Also send complete data to passenger service for frontend display
        channel.basic_publish(
            exchange='broker',
            routing_key='backend.location.passenger',
            body=json.dumps({
                'vin': vin,
                'frontDistance': distance_front,
                'rearDistance': distance_back,
                'frontChangeRate': change_rate_front,
                'rearChangeRate': change_rate_back,
                'speed': vehicle_speed
            }).encode('utf-8')
        )

        logger.info(f"Published distance data for {vin}: front={distance_front:.2f}m, back={distance_back:.2f}m")

    except Exception as e:
        logger.error(f"Failed to publish distance data: {e}")
        # Try to reconnect
        init_rabbitmq()

@app.route('/data', methods=['POST'])
def receive_data():
    global last_time_stamp, last_distance_front, last_distance_back, vehicle_vin, vehicle_speed

    try:
        data = request.get_json()

        # Extract data
        vin = data.get('vin')
        distance_front = float(data.get('distance_front', 0))
        distance_back = float(data.get('distance_back', 0))

        # Store vehicle info
        vehicle_vin = vin

        # Calculate speed from location data if available
        if 'speed' in data:
            vehicle_speed = data['speed']

        logger.info(f"Received distance data for {vin}: front={distance_front}m, back={distance_back}m")

        # Calculate change rates
        time_now = time.time()
        change_rate_front = 0
        change_rate_back = 0

        if last_time_stamp > 0:  # Skip first iteration
            time_diff = time_now - last_time_stamp
            if time_diff > 0:
                change_rate_front = (distance_front - last_distance_front) / time_diff  # m/s
                change_rate_back = (distance_back - last_distance_back) / time_diff  # m/s

                logger.debug(f"Change rates: front={change_rate_front:.2f} m/s, back={change_rate_back:.2f} m/s")

        # Update last values
        last_time_stamp = time_now
        last_distance_front = distance_front
        last_distance_back = distance_back

        # Publish to message broker
        publish_distance_data(vin, distance_front, distance_back, change_rate_front, change_rate_back)

        # Check critical conditions
        if distance_front < CRITICAL_DISTANCE_FRONT:
            logger.warning(f"CRITICAL: Front distance {distance_front}m is below threshold!")

        return jsonify({"status": "ok", "message": "Distance data processed"}), 200

    except Exception as e:
        logger.error(f"Error processing data: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    global connection, channel

    health_status = {
        "status": "healthy",
        "rabbitmq_connected": connection and not connection.is_closed if connection else False,
        "vehicle_vin": vehicle_vin,
        "last_update": last_time_stamp
    }

    return jsonify(health_status), 200

# Initialize RabbitMQ in a separate thread
def rabbitmq_init_thread():
    init_rabbitmq()

if __name__ == '__main__':
    # Initialize RabbitMQ connection
    rabbitmq_thread = threading.Thread(target=rabbitmq_init_thread, daemon=True)
    rabbitmq_thread.start()

    # Give RabbitMQ time to connect
    time.sleep(2)

    # Start Flask app
    logger.info("Starting Distance Monitor service...")
    app.run(host='0.0.0.0', port=5000)