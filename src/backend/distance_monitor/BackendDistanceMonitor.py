import threading
import time
import pika
import json
import os
import logging
from pika.exceptions import AMQPConnectionError
from collections import defaultdict

### CONSTANTS START ###
RETRY_WAIT = 5
# Emergency brake conditions (from PDF page 9)
CONDITION_1_DISTANCE = 20  # meters
CONDITION_1_RATE = 3  # m/s (decreasing)
CONDITION_2_DISTANCE = 40  # meters
CONDITION_2_RATE = 5  # m/s (decreasing)
### CONSTANTS END ###

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Store vehicle distance data for rate calculation
vehicle_distances = defaultdict(lambda: {
    'front_distance': None,
    'last_front_distance': None,
    'last_update_time': None
})

def calculate_change_rate(current_distance, last_distance, time_diff):
    """Calculate distance change rate in m/s"""
    if last_distance is None or time_diff == 0:
        return 0
    return (current_distance - last_distance) / time_diff

def check_emergency_conditions(distance, change_rate):
    """Check if emergency brake conditions are met"""
    # Check conditions (negative change_rate means decreasing distance)
    if distance < CONDITION_1_DISTANCE and change_rate < -CONDITION_1_RATE:
        return True
    if distance < CONDITION_2_DISTANCE and change_rate < -CONDITION_2_RATE:
        return True
    return False

def vehicle_dm_callback(ch, method, properties, body):
    """Process messages from Vehicle Distance Monitor"""
    try:
        data = json.loads(body.decode('utf-8'))
        vin = data.get('vin')
        dst_front = float(data.get('dst_front', 0))
        current_time = time.time()

        logger.info(f"Backend DM received from Vehicle DM - VIN: {vin}, Front: {dst_front}m")

        # Get previous data for this vehicle
        vehicle = vehicle_distances[vin]

        # Calculate change rate
        front_rate = 0
        if vehicle['last_update_time'] is not None:
            time_diff = current_time - vehicle['last_update_time']
            if vehicle['last_front_distance'] is not None:
                front_rate = calculate_change_rate(dst_front, vehicle['last_front_distance'], time_diff)

        # Update stored values
        vehicle['last_front_distance'] = vehicle['front_distance']
        vehicle['front_distance'] = dst_front
        vehicle['last_update_time'] = current_time

        # Check emergency conditions - Backend DM can also trigger EB!
        if check_emergency_conditions(dst_front, front_rate):
            logger.warning(f"EMERGENCY CONDITION MET! Vehicle {vin} - distance={dst_front}m, rate={front_rate}m/s")

            # Send emergency brake command directly
            eb_command = {
                'vin': vin,
                'command': 'emergency_stop',
                'reason': f"Backend DM: Critical distance {dst_front:.1f}m, rate {abs(front_rate):.1f}m/s",
                'source': 'backend_dm',
                'timestamp': current_time
            }

            ch.basic_publish(
                exchange='broker',
                routing_key=f'vehicle.{vin}.emergency.break',  # Direct to vehicle EB
                body=json.dumps(eb_command).encode('utf-8')
            )
            logger.info(f"Emergency brake triggered by Backend DM for {vin}")

        # Forward processed data to Central Director
        cd_data = {
            'vin': vin,
            'distance': dst_front,
            'change_rate': front_rate,
            'timestamp': current_time
        }

        # Send to Central Director
        ch.basic_publish(
            exchange='broker',
            routing_key='backend.distance.front',
            body=json.dumps(cd_data).encode('utf-8')
        )

        # Also send to passenger for display
        display_data = {
            'vin': vin,
            'frontDistance': dst_front,
            'speed': data.get('speed', 0)
        }
        ch.basic_publish(
            exchange='broker',
            routing_key='backend.location.passenger',
            body=json.dumps(display_data).encode('utf-8')
        )

        logger.info(f"Backend DM forwarded to CD for {vin} (distance: {dst_front:.1f}m, rate: {front_rate:.2f}m/s)")

    except Exception as e:
        logger.error(f"Error processing vehicle DM message: {e}")

# RabbitMQ connection setup
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

# Main execution
not_succeeded = True
connection = None
while not_succeeded:
    try:
        connection = get_rabbitmq_connection()
        not_succeeded = False
    except AMQPConnectionError as e:
        logger.warning(f"Failed to connect: {repr(e)}. Retrying in {RETRY_WAIT} seconds.")
        time.sleep(RETRY_WAIT)

logger.info("Successfully connected to RabbitMQ")
channel = connection.channel()
channel.exchange_declare(exchange='broker', exchange_type='topic', durable=True)

# Create queue for receiving vehicle DM messages
dm_queue = channel.queue_declare(queue='backend_distance_monitor_queue', durable=True)

# Subscribe to messages from vehicle distance monitor
channel.queue_bind(
    exchange='broker',
    queue=dm_queue.method.queue,
    routing_key='backend.location.distance_monitor'
)

# Set up consumer
channel.basic_consume(
    queue=dm_queue.method.queue,
    on_message_callback=vehicle_dm_callback,
    auto_ack=True
)

logger.info("Backend Distance Monitor started. Subscribing to 'backend.location.distance_monitor'...")

try:
    channel.start_consuming()
except KeyboardInterrupt:
    logger.info("Stopping Backend Distance Monitor...")
    channel.stop_consuming()
    connection.close()
except Exception as e:
    logger.error(f"Backend Distance Monitor error: {e}")
    if connection and not connection.is_closed:
        connection.close()