import os
import json
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime
from flask import Flask, request, jsonify
import threading
import time
from math import radians, sin, cos, sqrt, atan2

# Constants
CONDITION_1_DISTANCE = 20
CONDITION_1_RATE = 3
CONDITION_2_DISTANCE = 40
CONDITION_2_RATE = 5
CONDITION_3_DEVIATION = 20

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

vehicle_data = {}
vehicle_locations = {}

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('CD_POSTGRES_HOST', 'cd-postgres'),
        database="cd_db",
        user=os.environ.get('CD_POSTGRES_USER', 'admin'),
        password=os.environ.get('CD_POSTGRES_PASSWORD', 'admin')
    )

def init_database():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
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
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

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
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO emergency_events (vin, timestamp, event_type, source, details)
            VALUES (%s, %s, %s, %s, %s)
        """, (vin, datetime.now(), event_type, source, json.dumps(details) if details else None))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Stored event: {event_type} for {vin}")
    except Exception as e:
        logger.error(f"Failed to store event: {e}")

def check_emergency_conditions(vin, dm_distance, change_rate, lt_distance=None):
    reasons = []
    if dm_distance is not None:
        if dm_distance < CONDITION_1_DISTANCE and change_rate < -CONDITION_1_RATE:
            reasons.append(f"Condition 1: distance={dm_distance}m < 20m, rate={abs(change_rate)}m/s > 3m/s")
        if dm_distance < CONDITION_2_DISTANCE and change_rate < -CONDITION_2_RATE:
            reasons.append(f"Condition 2: distance={dm_distance}m < 40m, rate={abs(change_rate)}m/s > 5m/s")
        if lt_distance is not None and abs(dm_distance - lt_distance) > CONDITION_3_DEVIATION:
            reasons.append(f"Condition 3: |DM({dm_distance}m) - LT({lt_distance}m)| = {abs(dm_distance - lt_distance)}m > 20m")
    return reasons

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/distance', methods=['POST'])
def receive_distance():
    try:
        data = request.get_json()
        vin = data.get('vin')
        distance = float(data.get('distance'))
        change_rate = float(data.get('change_rate', 0))

        if vin not in vehicle_data:
            vehicle_data[vin] = {}

        vehicle_data[vin]['dm_distance'] = distance
        vehicle_data[vin]['front_rate'] = change_rate

        logger.info(f"Received distance data for {vin}: {distance}m (rate: {change_rate}m/s)")

        # Get LT distance if available
        lt_distance = vehicle_data[vin].get('lt_distance')

        # Check emergency conditions
        reasons = check_emergency_conditions(vin, distance, change_rate, lt_distance)

        if reasons:
            logger.warning(f"EMERGENCY CONDITIONS MET for {vin}: {reasons}")
            store_event(vin, "triggered", "CD_Logic", {
                'dm_distance': distance,
                'lt_distance': lt_distance,
                'change_rate': change_rate,
                'reasons': reasons
            })

            # Trigger emergency brake
            # The colleague implementing emergency brake should provide HTTP endpoint
            # For now, we'll log it
            logger.info(f"Would trigger emergency brake for {vin}")

            return jsonify({
                "status": "emergency",
                "vin": vin,
                "reasons": reasons
            }), 200

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Error processing distance data: {e}")
        return jsonify({"error": str(e)}), 500

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

@app.route('/emergency', methods=['POST'])
def emergency_request():
    try:
        data = request.get_json()
        vin = data.get('vin')
        source = data.get('source', 'Unknown')

        logger.info(f"Emergency brake requested from {source} for {vin}")
        store_event(vin, "triggered", source, {
            'manual_trigger': True,
            'source': source
        })

        # Trigger emergency brake
        logger.info(f"Would trigger emergency brake for {vin}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Error processing emergency request: {e}")
        return jsonify({"error": str(e)}), 500

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
    init_database()
    app.run(host='0.0.0.0', port=5000)