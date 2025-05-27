import time
import pika
import os
import json
from flask import Flask, request, jsonify
import logging
from pika.exceptions import AMQPConnectionError

### CONSTANTS START ###
RETRY_WAIT = 5
CRITICAL_DISTANCE = 0.5  # Critical distance in meters
### CONSTANTS END ###

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

last_time_stamp = 0
last_distance_front = 0
last_distance_back = 0

# RabbitMQ connection
credentials = pika.PlainCredentials(
    username=os.environ['RABBITMQ_USER'],
    password=os.environ['RABBITMQ_PASSWORD']
)

def get_rabbitmq_connection():
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host='rabbitmq',
            port=int(os.environ.get('RABBITMQ_PORT', 5672)),
            credentials=credentials
        )
    )

# Initialize connection
not_succeeded = True
connection = None
while not_succeeded:
    try:
        connection = get_rabbitmq_connection()
        not_succeeded = False
    except AMQPConnectionError as e:
        logger.warning(f"Failed to establish connection due to error: {repr(e)}.\n Retrying in {RETRY_WAIT} seconds.")
        time.sleep(RETRY_WAIT)

logger.info("Successfully established connection to rabbitmq.")
channel = connection.channel()
channel.exchange_declare(exchange='broker', exchange_type='topic')

if channel.is_closed:
    logger.error("channel closed")
    raise Exception

@app.route('/data', methods=['POST'])
def receive_data():
    global channel
    global last_time_stamp
    global last_distance_front
    global last_distance_back

    data = request.get_json()
    distance_front = data["distance_front"]
    distance_back = data["distance_back"]

    logger.info(f"Received distance data: front={distance_front}m, back={distance_back}m")

    time_now = time.time()
    if last_time_stamp > 0:  # Skip first iteration
        time_diff = time_now - last_time_stamp
        change_rate_front = (distance_front - last_distance_front) / time_diff  # m/s
        change_rate_back = (distance_back - last_distance_back) / time_diff  # m/s

        # Log change rates for debugging
        logger.debug(f"Change rates: front={change_rate_front:.2f} m/s, back={change_rate_back:.2f} m/s")

    # Update last values for next iteration
    last_time_stamp = time_now
    last_distance_front = distance_front
    last_distance_back = distance_back

    # Publish distance data to message broker
    # These will be consumed by Central Director
    channel.basic_publish(
        exchange='broker',
        routing_key='backend.distance.back',
        body=str(distance_back).encode("utf-8")
    )

    channel.basic_publish(
        exchange='broker',
        routing_key='backend.distance.front',
        body=str(distance_front).encode("utf-8")
    )

    # Check critical distance and log
    # Central Director will handle the actual emergency brake trigger
    if distance_front < CRITICAL_DISTANCE:
        logger.warning(f"WARNING: Front distance {distance_front}m is critical! Central Director will handle emergency response.")

    return jsonify({"status": "ok"}), 200

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    # Start Flask app
    app.run(host='0.0.0.0', port=5000)