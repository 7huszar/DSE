import pika
import os
import json
from flask import Flask, request, jsonify
import logging

from pika.exceptions import AMQPConnectionError

### CONSTANTS START ###

RETRY_WAIT = 5

### CONSTANTS END ###

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

logger.info("Successfully established connection to rabbitmq.")

channel = connection.channel()
channel.exchange_declare(exchange='broker', exchange_type='topic')

if channel.is_closed:
    logger.error("channel closed")
    raise Exception

@app.route('/data', methods=['POST'])
def receive_data():
    global channel
    distance = request.get_json()["distance_front"]
    logger.info(f"Received distance data: {str(distance)}")

    channel.basic_publish(
        exchange='broker',
        routing_key='backend.distance.monitor',
        body=json.dumps(distance).encode("utf-8")
    )

    if(distance < 0.5):
        logger.info("Distance is less than 0.5m! Emergency stop initiated.")

    return jsonify({"status": "ok"}), 200

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    # Start location sender in background

    # Start Flask app
    app.run(host='0.0.0.0', port=5000)