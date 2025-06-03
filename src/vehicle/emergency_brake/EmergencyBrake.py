import time
import pika
import os
import json
import logging
from pika.exceptions import AMQPConnectionError

### CONSTANTS START ###
RETRY_WAIT = 5
### CONSTANTS END ###

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# RabbitMQ connection
credentials = pika.PlainCredentials(
    username=os.environ.get('RABBITMQ_USER', 'guest'),
    password=os.environ.get('RABBITMQ_PASSWORD', 'guest')
)

def get_rabbitmq_connection():
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.environ.get('RABBITMQ_HOST', 'rabbitmq'),
            port=int(os.environ.get('RABBITMQ_PORT', 5672)),
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
    )

def emergency_brake_callback(ch, method, properties, body):
    """Process emergency brake commands from Central Director"""
    try:
        command_data = json.loads(body.decode('utf-8'))
        vin = command_data.get('vin')
        command = command_data.get('command')
        reason = command_data.get('reason', 'emergency')

        logger.warning(f"EMERGENCY BRAKE ACTIVATED for {vin}: {reason}")

        if command == 'emergency_stop':
            # Send stop command to vehicle
            stop_command = {
                "vin": vin,
                "command": "stop",
                "velocity": 0,
                "reason": reason,
                "timestamp": time.time()
            }

            # Publish stop command for the specific vehicle
            channel.basic_publish(
                exchange='broker',
                routing_key=f'vehicle.{vin.lower()}.control',
                body=json.dumps(stop_command).encode('utf-8')
            )

            # Also publish general vehicle control message
            channel.basic_publish(
                exchange='broker',
                routing_key='vehicle.control.stop',
                body=json.dumps(stop_command).encode('utf-8')
            )

            # Notify passenger service for UI update
            ui_update = {
                "vin": vin,
                "emergencyBrake": True,
                "speed": 0,
                "reason": reason,
                "timestamp": time.time()
            }

            channel.basic_publish(
                exchange='broker',
                routing_key='backend.location.passenger',
                body=json.dumps(ui_update).encode('utf-8')
            )

            logger.info(f"Stop command sent for vehicle {vin}")

    except Exception as e:
        logger.error(f"Error processing emergency brake command: {e}")

# Setup RabbitMQ connection
not_succeeded = True
connection = None
channel = None

while not_succeeded:
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.exchange_declare(exchange='broker', exchange_type='topic', durable=True)
        not_succeeded = False
    except AMQPConnectionError as e:
        logger.warning(f"Failed to establish connection: {repr(e)}. Retrying in {RETRY_WAIT} seconds.")
        time.sleep(RETRY_WAIT)

logger.info("Successfully connected to RabbitMQ")

# Create queue for emergency brake commands
result = channel.queue_declare(queue='emergency_brake_queue', durable=True)
queue_name = result.method.queue

# Bind to emergency brake topic
channel.queue_bind(exchange='broker', queue=queue_name, routing_key='vehicle.emergency.brake')

# Start consuming
channel.basic_consume(queue=queue_name, on_message_callback=emergency_brake_callback, auto_ack=True)

logger.info("Emergency Brake Service started. Waiting for emergency commands...")
logger.info("Listening on routing key: vehicle.emergency.brake")

try:
    channel.start_consuming()
except KeyboardInterrupt:
    logger.info("Stopping Emergency Brake Service...")
    channel.stop_consuming()
    connection.close()
except Exception as e:
    logger.error(f"Emergency Brake Service error: {e}")
    if connection and not connection.is_closed:
        connection.close()