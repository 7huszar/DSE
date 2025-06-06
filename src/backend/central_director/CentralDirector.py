import os
import json
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from flask import Flask, request, jsonify
import time
import requests

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



# --- API Endpoints ---
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

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


    app.run(host='0.0.0.0', port=5000, debug=False)