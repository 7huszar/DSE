import time
import pika
import os
import json
import logging
import psycopg2
from datetime import datetime
from pika.exceptions import AMQPConnectionError
from collections import defaultdict
from math import radians, sin, cos, sqrt, atan2

### CONSTANTS START ###
RETRY_WAIT = 5
# Emergency brake conditions
CONDITION_1_DISTANCE = 20  # meters
CONDITION_1_RATE = 3       # m/s (decreasing)
CONDITION_2_DISTANCE = 40  # meters
CONDITION_2_RATE = 5       # m/s (decreasing)
CONDITION_3_DEVIATION = 20  # meters deviation between DM and LT
### CONSTANTS END ###

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Vehicle data storage
vehicle_distances = defaultdict(lambda: {'dm_distance': None, 'lt_distance': None, 'front_rate': 0})
vehicle_locations = {}  # Store latest GPS positions

# Database connection
def get_db_connection():
    """Get PostgreSQL database connection"""
    return psycopg2.connect(
        host=os.environ.get('CD_POSTGRES_HOST', 'cd-postgres'),
        database="cd_db",
        user=os.environ.get('CD_POSTGRES_USER', 'admin'),
        password=os.environ.get('CD_POSTGRES_PASSWORD', 'admin')
    )

# Initialize database
def init_database():
    """Initialize the database schema"""
    conn = get_db_connection()
    cur = conn.cursor()

    # Create emergency_events table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS emergency_events (
            id SERIAL PRIMARY KEY,
            vin VARCHAR(17) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            event_type VARCHAR(32) NOT NULL,
            source VARCHAR(32),
            details JSONB
        )
    """)

    conn.commit()
    cur.close()
    conn.close()
    logger.info("Database initialized")

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two GPS coordinates in meters"""
    R = 6371000  # Earth radius in meters
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi/2)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c

def store_event_to_db(vin, event_type, source=None, details=None):
    """Store an event in the database"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO emergency_events (vin, timestamp, event_type, source, details)
        VALUES (%s, %s, %s, %s, %s)
    """, (vin, datetime.now(), event_type, source, json.dumps(details) if details else None))

    conn.commit()
    cur.close()
    conn.close()

    logger.info(f"Stored event to DB: {event_type} for {vin}")

def check_emergency_conditions(vin, dm_distance, change_rate, lt_distance=None):
    """Check if emergency brake conditions are met"""
    reasons = []

    # Condition 1: distance < 20m and rate > 3m/s
    if dm_distance < CONDITION_1_DISTANCE and change_rate < -CONDITION_1_RATE:
        reasons.append(f"Condition 1: distance={dm_distance}m < 20m, rate={abs(change_rate)}m/s > 3m/s")

    # Condition 2: distance < 40m and rate > 5m/s
    if dm_distance < CONDITION_2_DISTANCE and change_rate < -CONDITION_2_RATE:
        reasons.append(f"Condition 2: distance={dm_distance}m < 40m, rate={abs(change_rate)}m/s > 5m/s")

    # Condition 3: deviation > 20m between DM and LT
    if lt_distance is not None and abs(dm_distance - lt_distance) > CONDITION_3_DEVIATION:
        reasons.append(f"Condition 3: |DM({dm_distance}m) - LT({lt_distance}m)| = {abs(dm_distance - lt_distance)}m > 20m")

    return reasons

def send_emergency_brake(channel, vin, reasons, distance, change_rate):
    """Send emergency brake command"""
    command = {
        'vin': vin,
        'command': 'emergency_stop',
        'reasons': reasons,
        'distance': distance,
        'change_rate': change_rate,
        'source': 'central_director',
        'timestamp': time.time()
    }

    # Send to vehicle emergency brake
    channel.basic_publish(
        exchange='broker',
        routing_key=f'vehicle.{vin}.emergency.break',
        body=json.dumps(command).encode('utf-8')
    )

    # Also notify passenger service
    channel.basic_publish(
        exchange='broker',
        routing_key='backend.location.passenger',
        body=json.dumps({
            'vin': vin,
            'emergencyBrake': True,
            'reasons': reasons
        }).encode('utf-8')
    )

    logger.info(f"Emergency brake command sent for {vin}!")

def distance_callback(ch, method, properties, body):
    """Process distance messages from Backend Distance Monitor"""
    try:
        data = json.loads(body.decode('utf-8'))
        vin = data.get('vin')
        distance = float(data.get('distance'))
        change_rate = float(data.get('change_rate', 0))

        # Store DM distance
        vehicle_distances[vin]['dm_distance'] = distance
        vehicle_distances[vin]['front_rate'] = change_rate

        logger.info(f"CD received DM data for {vin}: {distance}m (rate: {change_rate}m/s)")

        # Get LT distance if available
        lt_distance = vehicle_distances[vin].get('lt_distance')

        # Check all emergency conditions
        reasons = check_emergency_conditions(vin, distance, change_rate, lt_distance)

        if reasons:
            logger.warning(f"EMERGENCY CONDITIONS MET for {vin}: {reasons}")

            # Store event
            store_event_to_db(vin, "triggered", "DM", {
                'dm_distance': distance,
                'lt_distance': lt_distance,
                'change_rate': change_rate,
                'reasons': reasons
            })

            # Send emergency brake
            send_emergency_brake(ch, vin, reasons, distance, change_rate)

    except Exception as e:
        logger.error(f"Error processing distance message: {e}")

def location_callback(ch, method, properties, body):
    """Process location messages from Location Tracker"""
    try:
        data = json.loads(body.decode('utf-8'))
        vin = data.get('vin')
        lat = data.get('lat')
        long = data.get('long')

        # Store location
        vehicle_locations[vin] = {'lat': lat, 'long': long, 'time': time.time()}

        # Calculate distances between vehicles
        if len(vehicle_locations) >= 2:
            vins = list(vehicle_locations.keys())
            for i in range(len(vins)):
                for j in range(i+1, len(vins)):
                    vin1, vin2 = vins[i], vins[j]
                    loc1, loc2 = vehicle_locations[vin1], vehicle_locations[vin2]

                    distance = calculate_distance(
                        loc1['lat'], loc1['long'],
                        loc2['lat'], loc2['long']
                    )

                    # Store LT distances for comparison with DM
                    vehicle_distances[vin1]['lt_distance'] = distance
                    vehicle_distances[vin2]['lt_distance'] = distance

                    logger.debug(f"LT distance between {vin1} and {vin2}: {distance:.1f}m")

    except Exception as e:
        logger.error(f"Error processing location message: {e}")

def emergency_request_callback(ch, method, properties, body):
    """Process emergency brake requests from Visor"""
    try:
        data = json.loads(body.decode('utf-8'))
        vin = data.get('vin')
        source = data.get('source', 'Unknown')

        logger.info(f"Emergency brake requested from {source} for {vin}")

        # Store event
        store_event_to_db(vin, "triggered", source, {
            'manual_trigger': True,
            'source': source
        })

        # Send emergency brake
        send_emergency_brake(ch, vin, [f"Manual trigger from {source}"], 0, 0)

    except Exception as e:
        logger.error(f"Error processing emergency request: {e}")

# Initialize database first
try:
    init_database()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    time.sleep(5)

# Setup RabbitMQ connection
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

# Connect to RabbitMQ
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
emergency_queue = channel.queue_declare(queue='central_director_emergency_queue', durable=True)

# Bind queues
channel.queue_bind(exchange='broker', queue=location_queue.method.queue, routing_key='backend.location.tracker')
channel.queue_bind(exchange='broker', queue=distance_queue.method.queue, routing_key='backend.distance.front')
channel.queue_bind(exchange='broker', queue=emergency_queue.method.queue, routing_key='backend.emergency.request')

# Set up consumers
channel.basic_consume(queue=distance_queue.method.queue, on_message_callback=distance_callback, auto_ack=True)
channel.basic_consume(queue=location_queue.method.queue, on_message_callback=location_callback, auto_ack=True)
channel.basic_consume(queue=emergency_queue.method.queue, on_message_callback=emergency_request_callback, auto_ack=True)

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