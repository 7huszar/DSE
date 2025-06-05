import time
import pika
import os
import json
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime
from pika.exceptions import AMQPConnectionError
from collections import defaultdict
from math import radians, sin, cos, sqrt, atan2
import threading

### CONSTANTS START ###
RETRY_WAIT = 5
CONDITION_1_DISTANCE = 20
CONDITION_1_RATE = 3
CONDITION_2_DISTANCE = 40
CONDITION_2_RATE = 5
CONDITION_3_DEVIATION = 20
EVENT_LOG_PUBLISH_INTERVAL = 10
EVENT_LOG_ROUTING_KEY = 'cd.data.eventlog'
### CONSTANTS END ###

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

vehicle_distances = defaultdict(lambda: {'dm_distance': None, 'lt_distance': None, 'front_rate': 0})
vehicle_locations = {}

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('CD_POSTGRES_HOST', 'cd-postgres'),
        database="cd_db",
        user=os.environ.get('CD_POSTGRES_USER', 'admin'),
        password=os.environ.get('CD_POSTGRES_PASSWORD', 'admin')
    )

def init_database():
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

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = radians(lat1); phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1); delta_lambda = radians(lon2 - lon1)
    a = sin(delta_phi/2)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def store_event_to_db(vin, event_type, source=None, details=None):
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
    reasons = []
    if dm_distance is not None:
        if dm_distance < CONDITION_1_DISTANCE and change_rate < -CONDITION_1_RATE:
            reasons.append(f"Condition 1: distance={dm_distance}m < 20m, rate={abs(change_rate)}m/s > 3m/s")
        if dm_distance < CONDITION_2_DISTANCE and change_rate < -CONDITION_2_RATE:
            reasons.append(f"Condition 2: distance={dm_distance}m < 40m, rate={abs(change_rate)}m/s > 5m/s")
        if lt_distance is not None and abs(dm_distance - lt_distance) > CONDITION_3_DEVIATION:
            reasons.append(f"Condition 3: |DM({dm_distance}m) - LT({lt_distance}m)| = {abs(dm_distance - lt_distance)}m > 20m")
    return reasons

def send_emergency_brake(channel, vin, reasons, distance, change_rate):
    command = {'vin': vin, 'command': 'emergency_stop', 'reasons': reasons, 'distance': distance, 'change_rate': change_rate, 'source': 'central_director', 'timestamp': time.time()}
    channel.basic_publish(exchange='broker', routing_key=f'vehicle.{vin}.emergency.break', body=json.dumps(command).encode('utf-8'))
    channel.basic_publish(exchange='broker', routing_key='backend.location.passenger', body=json.dumps({'vin': vin, 'emergencyBrake': True, 'reasons': reasons}).encode('utf-8'))
    logger.info(f"Emergency brake command sent for {vin}!")

def distance_callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode('utf-8'))
        vin = data.get('vin'); distance = float(data.get('distance')); change_rate = float(data.get('change_rate', 0))
        vehicle_distances[vin]['dm_distance'] = distance; vehicle_distances[vin]['front_rate'] = change_rate
        logger.info(f"CD received DM data for {vin}: {distance}m (rate: {change_rate}m/s)")
        lt_distance = vehicle_distances[vin].get('lt_distance')
        reasons = check_emergency_conditions(vin, distance, change_rate, lt_distance)
        if reasons:
            logger.warning(f"EMERGENCY CONDITIONS MET for {vin}: {reasons}")
            store_event_to_db(vin, "triggered", "CD_Logic", {'dm_distance': distance, 'lt_distance': lt_distance, 'change_rate': change_rate, 'reasons': reasons})
            send_emergency_brake(ch, vin, reasons, distance, change_rate)
    except Exception as e: logger.error(f"Error processing distance message: {e}", exc_info=True)

def location_callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode('utf-8'))
        vin = data.get('vin'); lat = data.get('lat'); long = data.get('long')
        vehicle_locations[vin] = {'lat': lat, 'long': long, 'time': data.get('time', time.time())}
        if len(vehicle_locations) >= 2:
            other_vins = [ov for ov in vehicle_locations if ov != vin]
            if other_vins:
                other_vin = other_vins[0]
                loc_self = vehicle_locations[vin]; loc_other = vehicle_locations[other_vin]
                if all(k in loc_self for k in ('lat', 'long')) and all(k in loc_other for k in ('lat', 'long')):
                    distance = calculate_distance(loc_self['lat'], loc_self['long'], loc_other['lat'], loc_other['long'])
                    vehicle_distances[vin]['lt_distance'] = distance
    except Exception as e: logger.error(f"Error processing location message: {e}", exc_info=True)

def emergency_request_callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode('utf-8'))
        vin = data.get('vin'); source = data.get('source', 'Unknown')
        logger.info(f"Emergency brake requested from {source} for {vin}")
        store_event_to_db(vin, "triggered", source, {'manual_trigger': True, 'source': source})
        send_emergency_brake(ch, vin, [f"Manual trigger from {source}"], 0, 0)
    except Exception as e: logger.error(f"Error processing emergency request: {e}", exc_info=True)

try:
    init_database()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    time.sleep(5)

credentials = pika.PlainCredentials(username=os.environ.get('RABBITMQ_USER', 'guest'), password=os.environ.get('RABBITMQ_PASSWORD', 'guest'))
def get_rabbitmq_connection():
    return pika.BlockingConnection(pika.ConnectionParameters(host=os.environ.get('RABBITMQ_HOST', 'rabbitmq'), port=int(os.environ.get('RABBITMQ_PORT', 5672)), credentials=credentials, heartbeat=600, blocked_connection_timeout=300))

_channel_for_publisher_cd = None
_publisher_stop_event_cd = threading.Event()

def _publish_event_log_data_cd_task():
    global _channel_for_publisher_cd
    logger.info("CD Event Log Publisher thread started.")
    while not _publisher_stop_event_cd.is_set():
        conn_db_cd = None
        try:
            if _channel_for_publisher_cd and _channel_for_publisher_cd.is_open:
                conn_db_cd = get_db_connection()
                with conn_db_cd.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("SELECT vin, timestamp, event_type, source, details FROM emergency_events ORDER BY timestamp DESC LIMIT 50")
                    events = cur.fetchall()
                    if events:
                        for event_item in events: # Renamed 'event' to 'event_item' to avoid conflict with threading.Event
                            if 'timestamp' in event_item and isinstance(event_item['timestamp'], datetime):
                                event_item['timestamp'] = event_item['timestamp'].isoformat()
                        message_body = json.dumps({"events": events})
                        _channel_for_publisher_cd.basic_publish(exchange='broker', routing_key=EVENT_LOG_ROUTING_KEY, body=message_body.encode('utf-8'))
            for _ in range(EVENT_LOG_PUBLISH_INTERVAL):
                if _publisher_stop_event_cd.is_set(): break
                time.sleep(1)
        except Exception as e:
            logger.error(f"CD Error in periodic_publisher thread: {e}", exc_info=True)
            time.sleep(EVENT_LOG_PUBLISH_INTERVAL)
        finally:
            if conn_db_cd: conn_db_cd.close()
    logger.info("CD Event Log Publisher thread stopped.")

not_succeeded = True
connection = None
publisher_thread_cd = None

while not_succeeded:
    try:
        connection = get_rabbitmq_connection()
        not_succeeded = False
        logger.info("Successfully connected to RabbitMQ")
        channel = connection.channel()
        channel.exchange_declare(exchange='broker', exchange_type='topic', durable=True)
        _channel_for_publisher_cd = channel

        distance_queue = channel.queue_declare(queue='central_director_distance_queue', durable=True)
        location_queue = channel.queue_declare(queue='central_director_location_queue', durable=True)
        emergency_queue = channel.queue_declare(queue='central_director_emergency_queue', durable=True)

        channel.queue_bind(exchange='broker', queue=location_queue.method.queue, routing_key='backend.location.tracker')
        channel.queue_bind(exchange='broker', queue=distance_queue.method.queue, routing_key='backend.distance.front')
        channel.queue_bind(exchange='broker', queue=emergency_queue.method.queue, routing_key='backend.emergency.request')

        channel.basic_consume(queue=distance_queue.method.queue, on_message_callback=distance_callback, auto_ack=True)
        channel.basic_consume(queue=location_queue.method.queue, on_message_callback=location_callback, auto_ack=True)
        channel.basic_consume(queue=emergency_queue.method.queue, on_message_callback=emergency_request_callback, auto_ack=True)
        logger.info("Central Director started. Monitoring vehicle distances...")

        if publisher_thread_cd is None or not publisher_thread_cd.is_alive():
            _publisher_stop_event_cd.clear()
            publisher_thread_cd = threading.Thread(target=_publish_event_log_data_cd_task, daemon=True)
            publisher_thread_cd.start()

        channel.start_consuming()
    except AMQPConnectionError as e:
        logger.warning(f"Failed to connect: {repr(e)}. Retrying in {RETRY_WAIT} seconds.")
        not_succeeded = True
        _channel_for_publisher_cd = None
        if publisher_thread_cd and publisher_thread_cd.is_alive():
            _publisher_stop_event_cd.set()
            publisher_thread_cd.join(timeout=2)
            publisher_thread_cd = None
        if connection and not connection.is_closed:
            try: connection.close()
            except: pass
        time.sleep(RETRY_WAIT)
    except KeyboardInterrupt:
        logger.info("Stopping Central Director...")
        _publisher_stop_event_cd.set()
        if publisher_thread_cd and publisher_thread_cd.is_alive():
            publisher_thread_cd.join(timeout=EVENT_LOG_PUBLISH_INTERVAL + 2)
        not_succeeded = False
        break
    except Exception as e:
        logger.error(f"Central Director error: {e}", exc_info=True)
        not_succeeded = True
        _channel_for_publisher_cd = None
        if publisher_thread_cd and publisher_thread_cd.is_alive():
            _publisher_stop_event_cd.set()
            publisher_thread_cd.join(timeout=2)
            publisher_thread_cd = None
        if connection and not connection.is_closed:
            try: connection.close()
            except: pass
        time.sleep(RETRY_WAIT)
    finally:
        if not not_succeeded:
            if connection and not connection.is_closed:
                try:
                    connection.close()
                except Exception as e_close:
                    logger.error(f"CD Error closing connection in finally: {e_close}")