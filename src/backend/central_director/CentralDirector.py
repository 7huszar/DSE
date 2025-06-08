import os
import json
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from flask import Flask, request, jsonify
import time
import pika

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("CentralDirector")

app = Flask(__name__)

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

def store_event(vin, source=None, reason=None):
    #Store the emergency brake event in the database
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO emergency_events (vin, timestamp, source, reason)
            VALUES (%s, %s, %s, %s)
        """, (vin, datetime.now(timezone.utc), source, reason))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Stored emergency brake event for vin {vin} from source {source} for reason {reason} in DB")
    except Exception as e:
        logger.error(f"Failed to store event for {vin}: {e}", exc_info=True)


def trigger_emergency_brake_on_vehicle(vin, rsn, src):
    #Send a rabbitMQ message to the vehicles emergency break service
    logger.warning(f"ACTION: Triggering emergency brake for VIN {vin}.")
    RABBITMQ_USER = os.environ['RABBITMQ_USER']
    RABBITMQ_PWD = os.environ['RABBITMQ_PASSWORD']
    RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
    RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    credentials = pika.PlainCredentials(
        username=RABBITMQ_USER,
        password=RABBITMQ_PWD
    )

    logger.info(f"Initiated Distance Monitor for Vehicle with VIN {vin.upper()}")
    consumer_connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials))

    if(consumer_connection == None):
        logger.error("Could not establish connection to RabbitMQ!")
    consumer_channel = consumer_connection.channel()

    routing_key = os.environ.get("EMERGENCY_BRAKE_FRONTEND").format(vin=vin.upper())

    logger.info(f"Routing key: {routing_key}")
    body = {
        "time": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "rsn": rsn,
        "src": src
    }
    consumer_channel.queue_declare('', exclusive=False)
    consumer_channel.exchange_declare(exchange=os.environ.get("BROKER_EXCHANGE"), exchange_type='topic', durable=True)
    consumer_channel.queue_bind('',exchange=os.environ.get("BROKER_EXCHANGE"), routing_key=routing_key)
    consumer_channel.basic_publish(exchange=os.environ.get("BROKER_EXCHANGE"), routing_key=routing_key, body=json.dumps(body).encode("utf-8"))

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
        store_event(vin=vin, source=source, reason=reason)

        # This is the new action
        trigger_emergency_brake_on_vehicle(vin=vin, src=data.get("src"), rsn=data.get("rsn"))

        return jsonify({"status": "ok, command sent", time: datetime.now(timezone.utc).isoformat(timespec="microseconds")}), 200
    except Exception as e:
        logger.error(f"Error processing emergency request: {e}", exc_info=True)
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/events', methods=['GET'])
def get_events():
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT vin, timestamp, source, reason
                FROM emergency_events
                ORDER BY timestamp DESC
                LIMIT 50
            """)
            events = cur.fetchall()

            for event in events:
                if 'timestamp' in event and isinstance(event['timestamp'], datetime):
                    event['timestamp'] = event['timestamp'].isoformat()

        conn.close()
        return jsonify({"events": events}), 200

    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_database()
    app.run(host=os.getenv("FLASK_PORT", "0.0.0.0"), port=int(os.getenv("FLASK_PORT", 5000)), debug=False)