import time
import pika
import os
import json
import logging
import requests
from pika.exceptions import AMQPConnectionError

### CONSTANTS START ###
RETRY_WAIT = 5
DATA_MOCK_URL = "http://data-mock-service/stop"  # URL to send stop command
### CONSTANTS END ###

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

# Callback for emergency brake commands
def emergency_brake_callback(ch, method, properties, body):
    """Process emergency brake commands from Central Director"""
    try:
        command_data = json.loads(body.decode('utf-8'))
        logger.warning(f"EMERGENCY BRAKE ACTIVATED: {command_data}")

        if command_data.get('command') == 'emergency_stop':
            # Send stop command to Data Mock via message broker
            # Publishing to a topic that Data Mock will listen to
            channel.basic_publish(
                exchange='broker',
                routing_key='vehicle.control.stop',
                body=json.dumps({
                    "command": "stop",
                    "velocity": 0,
                    "reason": command_data.get('reason', 'emergency'),
                    "timestamp": time.time()
                }).encode('utf-8')
            )
            logger.info("Stop command sent to vehicle!")

    except Exception as e:
        logger.error(f"Error processing emergency brake command: {e}")

# Setup RabbitMQ connection
not_succeeded = True
connection = None
while not_succeeded:
    try:
        connection = get_rabbitmq_connection()
        not_succeeded = False
    except AMQPConnectionError as e:
        logger.warning(f"Failed to establish connection: {repr(e)}. Retrying in {RETRY_WAIT} seconds.")
        time.sleep(RETRY_WAIT)

logger.info("Successfully connected to RabbitMQ")
channel = connection.channel()
channel.exchange_declare(exchange='broker', exchange_type='topic')

# Create queue for emergency brake commands
result = channel.queue_declare(queue='emergency_brake_queue', exclusive=False)
queue_name = result.method.queue

# Bind to emergency brake topic
channel.queue_bind(exchange='broker', queue=queue_name, routing_key='vehicle.emergency.brake')

# Start consuming
channel.basic_consume(queue=queue_name, on_message_callback=emergency_brake_callback, auto_ack=True)

logger.info("Emergency Brake Service started. Waiting for emergency commands...")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    logger.info("Stopping Emergency Brake Service...")
    channel.stop_consuming()
    connection.close()