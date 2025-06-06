import os
import json
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from flask import Flask, request, jsonify
import threading
import time
import requests
from math import radians, sin, cos, sqrt, atan2
import pika

# Constants
CONDITION_1_DISTANCE = 20
CONDITION_1_RATE = 3
CONDITION_2_DISTANCE = 40
CONDITION_2_RATE = 5
CONDITION_3_DEVIATION = 20

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("CentralDirector")

app = Flask(__name__)

# In-memory state
vehicle_data = {}
vehicle_locations = {}

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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS emergency_events (
                id SERIAL PRIMARY KEY,
                vin VARCHAR(20) NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                source VARCHAR(50),
                details JSONB
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    a = sin(delta_phi/2)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def store_event(vin, event_type, source=None, details=None):
    # Store a significant event in the database
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO emergency_events (vin, timestamp, event_type, source, details)
            VALUES (%s, %s, %s, %s, %s)
        """, (vin, datetime.now(timezone.utc), event_type, source, json.dumps(details) if details else None))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Stored event: '{event_type}' for VIN {vin}")
    except Exception as e:
        logger.error(f"Failed to store event for {vin}: {e}", exc_info=True)

# --- Core Logic ---
def check_emergency_conditions(vin, dm_distance, change_rate, lt_distance=None):
    reasons = []
    decreasing_rate = -change_rate
    if dm_distance is not None:
        if dm_distance < CONDITION_1_DISTANCE and decreasing_rate > CONDITION_1_RATE:
            reasons.append(f"Condition 1: distance={dm_distance:.2f}m < 20m and approach_rate={decreasing_rate:.2f}m/s > 3m/s")
        if dm_distance < CONDITION_2_DISTANCE and decreasing_rate > CONDITION_2_RATE:
            reasons.append(f"Condition 2: distance={dm_distance:.2f}m < 40m and approach_rate={decreasing_rate:.2f}m/s > 5m/s")
    if dm_distance is not None and lt_distance is not None:
        if abs(dm_distance - lt_distance) > CONDITION_3_DEVIATION:
            reasons.append(f"Condition 3: Plausibility failed. |DM({dm_distance:.2f}m) - LT({lt_distance:.2f}m)| = {abs(dm_distance - lt_distance):.2f}m > 20m")
    return list(dict.fromkeys(reasons))

def trigger_emergency_brake_on_vehicle(vin):
    """Sends an HTTP request to the vehicle's Emergency Brake service."""
    logger.warning(f"ACTION: Triggering emergency brake for VIN {vin}.")
    # The service name must be predictable. Assuming 'emergency-brake-<vin_lower>'.
    # Your EmergencyBrake service listens on /trigger.
    eb_service_url = f"http://emergency-brake-{vin.lower()}/trigger"
    try:
        # Send the command to the vehicle's microservice
        response = requests.post(eb_service_url, json={'time': time.time()}, timeout=3)
        if response.status_code == 200:
            logger.info(f"Successfully sent emergency brake command to VIN {vin}.")
            store_event(vin, "emergency_brake_command_sent", "CentralDirector")
        else:
            # Log failure if the vehicle service does not respond with 200 OK
            logger.error(f"Failed to trigger emergency brake for {vin}. Status: {response.status_code}, Body: {response.text}")
            store_event(vin, "emergency_brake_command_failed", "CentralDirector", {'status': response.status_code, 'body': response.text})
    except requests.exceptions.RequestException as e:
        # Log failure if the service is unreachable
        logger.error(f"Error connecting to Emergency Brake service for {vin} at {eb_service_url}: {e}")
        store_event(vin, "emergency_brake_command_failed", "CentralDirector", {'error': 'unreachable', 'details': str(e)})

# RabbitMQ Consumer für Emergency Brake Acknowledgments
def rabbitmq_consumer():
    """Consumes emergency brake acknowledgment messages from RabbitMQ."""
    while True:
        try:
            credentials = pika.PlainCredentials(
                username=os.environ.get('RABBITMQ_USER', 'guest'),
                password=os.environ.get('RABBITMQ_PASSWORD', 'guest')
            )
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=os.environ.get('RABBITMQ_HOST', 'rabbitmq'),
                    port=int(os.environ.get('RABBITMQ_PORT', 5672)),
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
            )
            channel = connection.channel()
            logger.info("Connected to RabbitMQ for emergency brake acknowledgments.")

            # Declare exchange and queue
            channel.exchange_declare(exchange='broker', exchange_type='topic', durable=True)
            queue = channel.queue_declare(queue='cd_emergency_brake_acks', durable=True)
            channel.queue_bind(
                exchange='broker',
                queue=queue.method.queue,
                routing_key='backend.location.tracker'
            )

            def callback(ch, method, properties, body):
                try:
                    data = json.loads(body.decode('utf-8'))
                    vin = data.get('vin', '').upper()
                    command = data.get('command')

                    if command == 'emergency_stop' and vin:
                        logger.info(f"Received emergency brake acknowledgment from {vin}")
                        store_event(
                            vin,
                            "emergency_brake_acknowledged",
                            data.get('source', 'Vehicle'),
                            {'reason': data.get('reason'), 'timestamp': data.get('timestamp')}
                        )
                except Exception as e:
                    logger.error(f"Error processing emergency brake ack: {e}", exc_info=True)

            channel.basic_consume(
                queue=queue.method.queue,
                on_message_callback=callback,
                auto_ack=True
            )

            logger.info("Started consuming emergency brake acknowledgments.")
            channel.start_consuming()

        except Exception as e:
            logger.error(f"RabbitMQ consumer error: {e}. Retrying in 5s...")
            time.sleep(5)

# --- API Endpoints ---
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/location', methods=['POST'])
def receive_location():
    try:
        data = request.get_json()
        vin = data.get('vin')
        lat = data.get('lat')
        long = data.get('long')

        vehicle_locations[vin] = {
            'lat': lat,
            'long': long,
            'time': data.get('time', time.time())
        }

        # Calculate distance to other vehicles
        if len(vehicle_locations) >= 2:
            other_vins = [v for v in vehicle_locations if v != vin]
            if other_vins:
                other_vin = other_vins[0]
                loc_self = vehicle_locations[vin]
                loc_other = vehicle_locations[other_vin]

                distance = calculate_distance(
                    loc_self['lat'], loc_self['long'],
                    loc_other['lat'], loc_other['long']
                )

                if vin not in vehicle_data:
                    vehicle_data[vin] = {}
                vehicle_data[vin]['lt_distance'] = distance

                logger.info(f"Calculated LT distance for {vin}: {distance}m")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Error processing location data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/distance', methods=['POST'])
def receive_distance():
    try:
        data = request.get_json()
        vin = data.get('vin')
        distance = float(data.get('distance'))
        change_rate = float(data.get('change_rate', 0))

        if vin not in vehicle_data: vehicle_data[vin] = {}
        vehicle_data[vin]['dm_distance'] = distance
        vehicle_data[vin]['change_rate'] = change_rate

        logger.debug(f"Received distance data for {vin}: {distance}m (rate: {change_rate}m/s)")

        lt_distance = vehicle_data[vin].get('lt_distance')
        reasons = check_emergency_conditions(vin, distance, change_rate, lt_distance)

        if reasons:
            logger.warning(f"EMERGENCY CONDITIONS MET for {vin}: {', '.join(reasons)}")
            store_event(vin, "emergency_condition_met", "CD_Logic", {'reasons': reasons})

            # This is the new action
            trigger_emergency_brake_on_vehicle(vin)

            return jsonify({"status": "emergency_triggered", "vin": vin, "reasons": reasons}), 200

        return jsonify({"status": "ok"}), 200
    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Error processing distance data due to bad format: {e}", exc_info=True)
        return jsonify({"error": "Invalid data format"}), 400
    except Exception as e:
        logger.error(f"Unexpected error in /distance endpoint: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route('/emergency', methods=['POST'])
def emergency_request():
    try:
        data = request.get_json()
        vin = data.get('vin')
        source = data.get('source', 'Unknown')
        logger.info(f"Manual emergency brake requested from '{source}' for {vin}")
        store_event(vin, "manual_emergency_request", source)

        # This is the new action
        trigger_emergency_brake_on_vehicle(vin)

        return jsonify({"status": "ok, command sent"}), 200
    except Exception as e:
        logger.error(f"Error processing emergency request: {e}", exc_info=True)
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/events', methods=['GET'])
def get_events():
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT vin, timestamp, event_type, source, details
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
    # Initialize the database before starting the web server
    init_database()

    consumer_thread = threading.Thread(target=rabbitmq_consumer, daemon=True)
    consumer_thread.start()
    logger.info("Started RabbitMQ consumer thread.")

    app.run(host='0.0.0.0', port=5000, debug=False)