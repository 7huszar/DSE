import time
import pika
import os
import json
import psycopg2
import logging
from datetime import datetime
from pika.exceptions import AMQPConnectionError

### CONSTANTS START ###
RETRY_WAIT = 5
CRITICAL_DISTANCE_THRESHOLD = 0.5  # meters
### CONSTANTS END ###

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Database connection
def get_db_connection():
    """Connect to the Central Director database"""
    return psycopg2.connect(
        host=os.environ.get('CD_DB_HOST', 'cd-postgres'),
        port=os.environ.get('CD_DB_PORT', 5432),
        database=os.environ.get('CD_DB_NAME', 'cd_db'),
        user=os.environ.get('CD_DB_USER', 'admin'),
        password=os.environ.get('CD_DB_PASSWORD', 'admin')
    )

# Create events table if not exists
def init_database():
    """Initialize the database with events table"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                                                      id SERIAL PRIMARY KEY,
                                                      time TIMESTAMP NOT NULL,
                                                      event VARCHAR(255) NOT NULL,
                    details JSONB
                    )
                """)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Database initialized")

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

# Store event in database
def store_event(event_type, details=None):
    """Store an event in the database"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO events (time, event, details) VALUES (%s, %s, %s)",
        (datetime.now(), event_type, json.dumps(details) if details else None)
    )
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Stored event: {event_type}")

# Callback for distance messages
def distance_callback(ch, method, properties, body):
    """Process distance messages from Distance Monitor"""
    try:
        distance = float(body.decode('utf-8'))
        routing_key = method.routing_key

        # Check if it's front distance
        if 'distance.front' in routing_key:
            logger.info(f"Received front distance: {distance}m")

            # Check if distance is critical
            if distance < CRITICAL_DISTANCE_THRESHOLD:
                logger.warning(f"CRITICAL: Front distance {distance}m is below threshold!")

                # Store event in database
                store_event("emergency_brake_triggered", {
                    "distance_front": distance,
                    "threshold": CRITICAL_DISTANCE_THRESHOLD,
                    "trigger_time": datetime.now().isoformat()
                })

                # Send emergency brake command
                channel.basic_publish(
                    exchange='broker',
                    routing_key='vehicle.emergency.brake',
                    body=json.dumps({
                        "command": "emergency_stop",
                        "reason": "front_distance_critical",
                        "distance": distance
                    }).encode('utf-8')
                )
                logger.info("Emergency brake command sent!")

    except Exception as e:
        logger.error(f"Error processing distance message: {e}")

# Initialize database
init_database()

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

# Create queue for distance monitoring
result = channel.queue_declare(queue='central_director_queue', exclusive=False)
queue_name = result.method.queue

# Bind to distance topics
channel.queue_bind(exchange='broker', queue=queue_name, routing_key='backend.distance.*')

# Start consuming
channel.basic_consume(queue=queue_name, on_message_callback=distance_callback, auto_ack=True)

logger.info("Central Director started. Waiting for messages...")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    logger.info("Stopping Central Director...")
    channel.stop_consuming()
    connection.close()