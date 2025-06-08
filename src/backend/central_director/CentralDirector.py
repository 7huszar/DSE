import os
import json
import logging
import signal
import sys
import threading

import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from flask import Flask, request, jsonify
import time
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("CentralDirector")

app = Flask(__name__)

RABBITMQ_USER = os.environ['RABBITMQ_USER']
RABBITMQ_PWD = os.environ['RABBITMQ_PASSWORD']
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
credentials = pika.PlainCredentials(
    username=RABBITMQ_USER,
    password=RABBITMQ_PWD
)

consumer_connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials))

if(consumer_connection == None):
    logger.error("Could not establish connection to RabbitMQ!")
consumer_channel = consumer_connection.channel()


CONSUMER_QUEUE = os.getenv("CENTRAL_DIRECTOR_QUEUE", "backend.central.director")
BROKER = os.environ.get("BROKER_EXCHANGE", "broker")
CONSUMER_ROUTING_KEY = os.getenv("CENTRAL_DIRECTOR_BACKEND", "backend.central.director")

consumer_channel.queue_declare(CONSUMER_QUEUE, exclusive=False)
consumer_channel.exchange_declare(exchange=BROKER, exchange_type='topic', durable=True)

consumer_channel.queue_bind(queue=CONSUMER_QUEUE, exchange=BROKER, routing_key=CONSUMER_ROUTING_KEY)

publisher_channel = consumer_connection.channel()

# --- Database Functions ---
def get_db_connection():
    # Connect to the database with a retry mechanism
    conn = None
    retries = 5
    while retries > 0 and conn is None:
        try:
            conn = psycopg2.connect(
                host=os.environ.get('CD_POSTGRES_HOST', 'cd-postgres'),
                database="cd_db",
                user=os.environ.get('CD_POSTGRES_USER', 'admin'),
                password=os.environ.get('CD_POSTGRES_PASSWORD', 'admin')
            )
            return conn
        except psycopg2.OperationalError as e:
            logger.warning(f"DB connection failed: {e}. Retrying in 5s... ({retries-1} left)")
            retries -= 1
            time.sleep(5)
    # If connection fails after all retries, raise an error
    raise ConnectionError("Could not establish database connection.")

def init_database():
    # Initialize the database table if it does not exist
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""DROP TABLE IF EXISTS emergency_events
                    """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS emergency_events (
                id SERIAL PRIMARY KEY,
                vin VARCHAR(20) NOT NULL,
                time TIMESTAMPTZ NOT NULL,
                src VARCHAR(255),
                rsn VARCHAR (255)
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)

def store_event(vin, source=None, reason=None, time=None):
    #Store the emergency brake event in the database
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO emergency_events (vin, time, src, rsn)
            VALUES (%s, %s, %s, %s)
        """, (vin, time, source, reason))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Stored emergency brake event for vin {vin} from source {source} for reason {reason} in DB")
    except Exception as e:
        logger.error(f"Failed to store event for {vin}: {e}", exc_info=True)

def callback(ch, method, properties, body):
    decoded = json.loads(body.decode("utf-8"))
    store_event(vin=decoded.get("vin"), source=decoded.get("src"), reason=decoded.get("rsn"), time=datetime.fromisoformat(decoded.get("time")))

def consume():
    global consumer_channel
    global logger

    consumer_channel.basic_consume(queue=CONSUMER_QUEUE, on_message_callback=callback, auto_ack=True)

    try:
        consumer_channel.start_consuming()
    except (AMQPConnectionError, AMQPChannelError) as e:
        logger.error(f"RabbitMQ connection failed while consuming {repr(e)}")
    finally:
        consumer_channel.close()

threading.Thread(target=consume).start()


def trigger_emergency_brake_on_vehicle(vin, rsn, src):
    #Send a rabbitMQ message to the vehicles emergency break service
    logger.warning(f"ACTION: Triggering emergency brake for VIN {vin}.")

    routing_key = os.environ.get("EMERGENCY_BRAKE").format(vin=vin.upper())

    logger.info(f"Routing key: {routing_key}")
    body = {
        "time": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "rsn": rsn,
        "src": src
    }
    publisher_channel.basic_publish(exchange=os.environ.get("BROKER_EXCHANGE"), routing_key=routing_key, body=json.dumps(body).encode("utf-8"))

    logger.info("Published emergency brake to frontend emergency brake via RabbitMQ!")

# --- API Endpoints ---
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/emergency/<vin>', methods=['POST'])
def emergency_request(vin):
    try:
        data = request.get_json()
        logger.info(data)
        source = data.get('src', 'Unknown source')
        reason = data.get('rsn', 'Unknown reason')
        logger.info(f"Manual emergency brake requested from '{source}' for {vin} because of {reason}")

        # This is the new action
        trigger_emergency_brake_on_vehicle(vin=vin, src=data.get("src"), rsn=data.get("rsn"))

        return jsonify({"status": "ok, command sent", "time": datetime.now(timezone.utc).isoformat(timespec="microseconds")}), 200
    except Exception as e:
        logger.error(f"Error processing emergency request: {e}", exc_info=True)
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/events', methods=['GET'])
def get_events():
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT vin, time, src, rsn
                FROM emergency_events
                ORDER BY time DESC
                LIMIT 50
            """)
            events = cur.fetchall()

            for event in events:
                if 'time' in event and isinstance(event['time'], datetime):
                    event['time'] = event['time'].isoformat(timespec="milliseconds")

        conn.close()
        return jsonify({"events": events}), 200

    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return jsonify({"error": str(e)}), 500

def handle_shutdown(self, signum, frame):
    global logger
    global consumer_channel
    global publisher_channel
    global consumer_connection

    logger.info(f"Received shutdown signal ({signum}), shutting down gracefully...")

    try:
        consumer_channel.close()
    except (AMQPConnectionError, AMQPChannelError) as e:
        logger.warning(f"Failed to close: {repr(e)}")

    try:
        publisher_channel.close()
    except (AMQPConnectionError, AMQPChannelError) as e:
        logger.warning(f"Failed to close: {repr(e)}")

    try:
        consumer_connection.close()
    except (AMQPConnectionError, AMQPChannelError) as e:
        logger.warning(f"Failed to close: {repr(e)}")


    logger.info("Shutdown complete.")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

if __name__ == '__main__':
    init_database()
    app.run(host=os.getenv("FLASK_PORT", "0.0.0.0"), port=int(os.getenv("FLASK_PORT", 5000)), debug=False)