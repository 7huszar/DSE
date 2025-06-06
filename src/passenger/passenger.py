from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pika
import json
import threading
import os
import time
import logging  # Added
import requests # Added

# --- Setup structured logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PassengerAPI")

# --- Environment Configuration ---
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.environ.get('RABBITMQ_USER')
RABBITMQ_PASSWORD = os.environ.get('RABBITMQ_PASSWORD')

# --- RabbitMQ Topics & Queues ---
EXCHANGE_NAME = 'broker'
EXCHANGE_TYPE = 'topic'
ROUTING_KEY_FOR_PASSENGER = 'backend.location.passenger'
PASSENGER_VISOR_QUEUE_NAME = 'passenger_service_visor_updates_queue'
CD_EVENT_LOG_ROUTING_KEY = 'cd.data.eventlog'

# --- Flask & SocketIO Setup ---
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- In-Memory Caches ---
vehicles_data_cache = {}
event_log_cache = []
event_log_cache_lock = threading.Lock()

# This function runs in a background thread to consume messages from RabbitMQ.
def rabbitmq_consumer_main_loop():
    global event_log_cache
    while True: # Main loop to handle reconnects
        if not RABBITMQ_USER or not RABBITMQ_PASSWORD:
            logger.critical("CRITICAL: RABBITMQ_USER or RABBITMQ_PASSWORD not set. Retrying in 10s.")
            time.sleep(10)
            continue
        try:
            logger.info(f"Connecting to RabbitMQ: {RABBITMQ_HOST}:{RABBITMQ_PORT} User: {RABBITMQ_USER}")
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            connection_params = pika.ConnectionParameters(
                host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials,
                heartbeat=600, blocked_connection_timeout=300
            )
            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()
            logger.info("Connected to RabbitMQ.")

            # Declare exchange and queues
            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type=EXCHANGE_TYPE, durable=True)
            channel.queue_declare(queue=PASSENGER_VISOR_QUEUE_NAME, durable=True)
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=PASSENGER_VISOR_QUEUE_NAME, routing_key=ROUTING_KEY_FOR_PASSENGER)
            logger.info(f"Queue '{PASSENGER_VISOR_QUEUE_NAME}' bound to RKey '{ROUTING_KEY_FOR_PASSENGER}'.")

            event_log_data_queue_name = 'passenger_event_log_data_queue'
            channel.queue_declare(queue=event_log_data_queue_name, durable=True)
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=event_log_data_queue_name, routing_key=CD_EVENT_LOG_ROUTING_KEY)
            logger.info(f"Queue '{event_log_data_queue_name}' bound to RKey '{CD_EVENT_LOG_ROUTING_KEY}'.")

            # Callback for Central Director event logs
            def cd_event_log_callback(ch, method, properties, body):
                global event_log_cache
                msg_str = body.decode('utf-8')
                try:
                    data = json.loads(msg_str)
                    # The spec for this is not defined, so we handle it defensively
                    if "events" in data and isinstance(data["events"], list):
                        with event_log_cache_lock:
                            event_log_cache = data["events"]
                    else:
                        logger.warning(f"Received CD event log data in unexpected format: {msg_str}")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e_cb:
                    logger.error(f"Error processing CD EventLog (Tag:{method.delivery_tag}): {e_cb}. NACKing.", exc_info=True)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            # Callback for vehicle data updates
            def message_processing_callback(ch, method, properties, body):
                msg_str = body.decode('utf-8')
                try:
                    data = json.loads(msg_str)
                    vin = data.get('vin')
                    if vin:
                        # Update cache and emit to frontend
                        current_vehicle_data = vehicles_data_cache.get(vin, {})
                        current_vehicle_data.update(data)
                        vehicles_data_cache[vin] = current_vehicle_data
                        socketio.emit('vehicle_update', current_vehicle_data)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error(f"Error processing message (Tag:{method.delivery_tag}): {e}. NACKing.", exc_info=True)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            # Start consuming from both queues
            channel.basic_consume(queue=PASSENGER_VISOR_QUEUE_NAME, on_message_callback=message_processing_callback, auto_ack=False)
            channel.basic_consume(queue=event_log_data_queue_name, on_message_callback=cd_event_log_callback, auto_ack=False)

            logger.info("Waiting for messages on all subscribed queues...")
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"AMQP Connection Error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in consumer loop: {e}", exc_info=True)

        logger.warning("Connection lost or error. Retrying in 10 seconds...")
        time.sleep(10)

# --- API Endpoints ---
@app.route('/vehicles', methods=['GET'])
def get_all_vehicles_api():
    return jsonify(list(vehicles_data_cache.values()))

@app.route('/vehicle/<string:vin>', methods=['GET'])
def get_specific_vehicle_api(vin):
    vehicle = vehicles_data_cache.get(vin)
    if vehicle:
        return jsonify(vehicle)
    return jsonify({"error": f"Vehicle VIN {vin} not found"}), 404

@app.route('/api/events', methods=['GET'])
def get_events_from_passenger_cache():
    vin_filter = request.args.get('vin')
    with event_log_cache_lock:
        current_events_copy = list(event_log_cache)
    if vin_filter:
        filtered_events = [event for event in current_events_copy if event.get('vin') == vin_filter]
        return jsonify(filtered_events), 200
    else:
        return jsonify(current_events_copy), 200

# Endpoint to forward emergency brake requests from the Visor.
@app.route('/emergency-brake', methods=['POST'])
def trigger_emergency_brake():
    data = request.get_json()
    vin = data.get('vin')
    source = data.get('source', 'Unknown')
    if not vin:
        logger.warning("Emergency brake request missing VIN.")
        return jsonify({"error": "VIN is required"}), 400

    try:
        # Forward the request to the Central Director service
        logger.info(f"Forwarding emergency brake request for VIN {vin} to Central Director.")
        response = requests.post(
            'http://central-director-service/emergency',
            json={
                'vin': vin,
                'source': source,
                'timestamp': time.time()
            },
            timeout=5
        )
        # Check if the upstream service responded successfully
        if response.status_code == 200:
            logger.info(f"Emergency brake request for {vin} forwarded successfully.")
            return jsonify({"status": "Emergency brake request sent", "vin": vin}), 200
        else:
            logger.error(f"Failed to forward emergency brake request. Upstream status: {response.status_code}")
            return jsonify({"error": "Failed to send emergency brake request to upstream service"}), 502

    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending emergency brake request: {e}", exc_info=True)
        return jsonify({"error": "Failed to connect to upstream service"}), 502

# --- Socket.IO Event Handlers ---
@socketio.on('connect')
def handle_socketio_client_connect():
    logger.info(f"Visor client connected (SID: {request.sid})")
    emit('connected', {'message': 'Connected to STEEER Visor Backend (Passenger)!'}, room=request.sid)

@socketio.on('disconnect')
def handle_socketio_client_disconnect():
    logger.info(f"Visor client disconnected (SID: {request.sid})")

# --- Main execution block ---
if __name__ == '__main__':
    logger.info("Initializing Passenger Service...")
    # Start the RabbitMQ consumer in a background thread
    consumer_thread = threading.Thread(target=rabbitmq_consumer_main_loop, name="RabbitMQConsumerThread", daemon=True)
    consumer_thread.start()
    logger.info("RabbitMQ Consumer Thread started.")
    logger.info(f"Starting Flask-SocketIO server on http://0.0.0.0:8080 ...")
    socketio.run(app, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True, debug=False)