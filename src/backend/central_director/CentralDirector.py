import time
import pika
import os
import json
import logging
from datetime import datetime
from pika.exceptions import AMQPConnectionError
from collections import defaultdict

### CONSTANTS START ###
RETRY_WAIT = 5
# Emergency brake conditions
CONDITION_1_DISTANCE = 20  # meters
CONDITION_1_RATE = 3       # m/s (decreasing)
CONDITION_2_DISTANCE = 40  # meters
CONDITION_2_RATE = 5       # m/s (decreasing)
### CONSTANTS END ###

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# In-memory storage for events and vehicle data
events_log = []
vehicle_distances = defaultdict(lambda: {'front': None, 'back': None, 'front_rate': 0, 'back_rate': 0})

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

def store_event(event_type, details=None):
    """Store an event in memory"""
    event = {
        'time': datetime.now().isoformat(),
        'event': event_type,
        'details': details
    }
    events_log.append(event)

    # Keep only last 1000 events
    if len(events_log) > 1000:
        events_log.pop(0)

    logger.info(f"Stored event: {event_type} - {details}")

def check_emergency_conditions(vin, distance, change_rate, direction='front'):
    """Check if emergency brake conditions are met"""
    if direction != 'front':
        return False

    # Check conditions (negative change_rate means decreasing distance)
    if distance < CONDITION_1_DISTANCE and change_rate < -CONDITION_1_RATE:
        logger.warning(f"EMERGENCY CONDITION 1: Vehicle {vin} - distance={distance}m, rate={change_rate}m/s")
        return True

    if distance < CONDITION_2_DISTANCE and change_rate < -CONDITION_2_RATE:
        logger.warning(f"EMERGENCY CONDITION 2: Vehicle {vin} - distance={distance}m, rate={change_rate}m/s")
        return True

    return False

def send_emergency_brake(channel, vin, reason, distance, change_rate):
    """Send emergency brake command"""
    command = {
        'vin': vin,
        'command': 'emergency_stop',
        'reason': reason,
        'distance': distance,
        'change_rate': change_rate,
        'timestamp': time.time()
    }

    # Send to emergency brake service
    channel.basic_publish(
        exchange='broker',
        routing_key='vehicle.emergency.brake',
        body=json.dumps(command).encode('utf-8')
    )

    # Also send to passenger service for frontend notification
    channel.basic_publish(
        exchange='broker',
        routing_key='backend.location.passenger',
        body=json.dumps({
            'vin': vin,
            'emergencyBrake': True,
            'reason': reason
        }).encode('utf-8')
    )

    logger.info(f"Emergency brake command sent for {vin}!")

def distance_callback(ch, method, properties, body):
    """Process distance messages from Distance Monitor"""
    try:
        data = json.loads(body.decode('utf-8'))
        routing_key = method.routing_key

        vin = data.get('vin')
        distance = float(data.get('distance'))
        change_rate = float(data.get('change_rate', 0))

        # Determine direction from routing key
        if 'distance.front' in routing_key:
            direction = 'front'
            vehicle_distances[vin]['front'] = distance
            vehicle_distances[vin]['front_rate'] = change_rate
            logger.info(f"Received front distance for {vin}: {distance}m (rate: {change_rate}m/s)")
        elif 'distance.back' in routing_key:
            direction = 'back'
            vehicle_distances[vin]['back'] = distance
            vehicle_distances[vin]['back_rate'] = change_rate
            logger.info(f"Received back distance for {vin}: {distance}m (rate: {change_rate}m/s)")
        else:
            return

        # Check emergency conditions for front distance
        if direction == 'front' and check_emergency_conditions(vin, distance, change_rate, direction):
            reason = f"Critical front distance: {distance:.1f}m, approaching at {abs(change_rate):.1f}m/s"

            # Store event
            store_event("emergency_brake_triggered", {
                'vin': vin,
                'distance_front': distance,
                'change_rate': change_rate,
                'conditions': f"distance < threshold AND decreasing rapidly",
                'trigger_time': datetime.now().isoformat()
            })

            # Send emergency brake command
            send_emergency_brake(ch, vin, reason, distance, change_rate)

    except Exception as e:
        logger.error(f"Error processing distance message: {e}")

def location_callback(ch, method, properties, body):
    """Process location messages from Location Tracker"""
    try:
        data = json.loads(body.decode('utf-8'))
        vin = data.get('vin')
        lat = data.get('lat')
        long = data.get('long')

        logger.debug(f"Location update for {vin}: ({lat}, {long})")

        # Here you could implement distance calculation between vehicles
        # For now, we rely on the Distance Monitor data

    except Exception as e:
        logger.error(f"Error processing location message: {e}")

# Setup RabbitMQ connection
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

# Create queues
distance_queue = channel.queue_declare(queue='central_director_distance_queue', durable=True)
location_queue = channel.queue_declare(queue='central_director_location_queue', durable=True)

# Bind queues to topics
channel.queue_bind(exchange='broker', queue=location_queue.method.queue, routing_key='backend.location.tracker')
channel.queue_bind(exchange='broker', queue=distance_queue.method.queue, routing_key='backend.distance.front')

# Set up consumers
channel.basic_consume(queue=distance_queue.method.queue, on_message_callback=distance_callback, auto_ack=True)
channel.basic_consume(queue=location_queue.method.queue, on_message_callback=location_callback, auto_ack=True)

logger.info("Central Director started. Monitoring vehicle distances...")

try:
    channel.start_consuming()
except KeyboardInterrupt:
    logger.info("Stopping Central Director...")
    channel.stop_consuming()
    connection.close()
except Exception as e:
    logger.error(f"Central Director error: {e}")
    if connection and not connection.is_closed:
        connection.close()