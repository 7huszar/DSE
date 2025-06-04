from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pika
import json
import threading
import os
import time

RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.environ.get('RABBITMQ_USER')
RABBITMQ_PASSWORD = os.environ.get('RABBITMQ_PASSWORD')

EXCHANGE_NAME = 'broker'
EXCHANGE_TYPE = 'topic'
ROUTING_KEY_FOR_PASSENGER = 'backend.location.passenger'
PASSENGER_VISOR_QUEUE_NAME = 'passenger_service_visor_updates_queue'

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

vehicles_data_cache = {}

def rabbitmq_consumer_main_loop():
    while True:
        if not RABBITMQ_USER or not RABBITMQ_PASSWORD:
            print("[Passenger-RabbitMQ] CRITICAL: RABBITMQ_USER or RABBITMQ_PASSWORD not set from environment. Retrying in 10s.")
            time.sleep(10)
            continue
        try:
            print(f"[Passenger-RabbitMQ] Connecting to RabbitMQ: {RABBITMQ_HOST}:{RABBITMQ_PORT} User: {RABBITMQ_USER}")
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            connection_params = pika.ConnectionParameters(
                host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials,
                heartbeat=600, blocked_connection_timeout=300
            )
            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()
            print("[Passenger-RabbitMQ] Connected to RabbitMQ.")

            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type=EXCHANGE_TYPE, durable=True)
            channel.queue_declare(queue=PASSENGER_VISOR_QUEUE_NAME, durable=True)
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=PASSENGER_VISOR_QUEUE_NAME, routing_key=ROUTING_KEY_FOR_PASSENGER)
            print(f"[Passenger-RabbitMQ] Queue '{PASSENGER_VISOR_QUEUE_NAME}' bound to RKey '{ROUTING_KEY_FOR_PASSENGER}'.")

            def message_processing_callback(ch, method, properties, body):
                msg_str = body.decode()
                print(f"[Passenger-RabbitMQ] Received (Tag:{method.delivery_tag}, RKey:{method.routing_key}): {msg_str[:100]}...") # Log only first 100 chars
                try:
                    data = json.loads(msg_str)
                    vin = data.get('vin')
                    if vin:
                        vehicles_data_cache[vin] = data
                        socketio.emit('vehicle_update', data) # Emit full data object
                        # print(f"[Passenger-SocketIO] Emitted 'vehicle_update' for VIN {vin}.") # Can be verbose
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    print(f"[Passenger-RabbitMQ] Error processing message (Tag:{method.delivery_tag}): {e}. NACKing.")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(queue=PASSENGER_VISOR_QUEUE_NAME, on_message_callback=message_processing_callback, auto_ack=False)
            print(f"[Passenger-RabbitMQ] Waiting for messages in Queue '{PASSENGER_VISOR_QUEUE_NAME}'.")
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            print(f"[Passenger-RabbitMQ] AMQP Connection Error: {e}")
        except Exception as e:
            print(f"[Passenger-RabbitMQ] Unexpected error in consumer loop: {e}")

        print("[Passenger-RabbitMQ] Connection lost or error. Retrying in 10 seconds...")
        time.sleep(10)

@app.route('/vehicles', methods=['GET'])
def get_all_vehicles_api():
    return jsonify(list(vehicles_data_cache.values()))

@app.route('/vehicle/<string:vin>', methods=['GET'])
def get_specific_vehicle_api(vin):
    vehicle = vehicles_data_cache.get(vin)
    if vehicle:
        return jsonify(vehicle)
    return jsonify({"error": f"Vehicle VIN {vin} not found"}), 404

@app.route('/emergency-brake', methods=['POST'])
def trigger_emergency_brake():
    """Handle emergency brake requests from Visor"""
    data = request.get_json()
    vin = data.get('vin')
    source = data.get('source', 'Unknown')

    if not vin:
        return jsonify({"error": "VIN is required"}), 400

    # Publish emergency brake request to Central Director
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials
        ))
        channel = connection.channel()

        message = {
            'vin': vin,
            'source': source,
            'timestamp': time.time()
        }

        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key='backend.emergency.request',
            body=json.dumps(message).encode('utf-8')
        )

        connection.close()
        return jsonify({"status": "Emergency brake request sent", "vin": vin}), 200
    except Exception as e:
        print(f"[Passenger] Error sending emergency brake request: {e}")
        return jsonify({"error": "Failed to send emergency brake request"}), 500

@socketio.on('connect')
def handle_socketio_client_connect():
    print(f"[Passenger-SocketIO] Client connected (SID: {request.sid})")
    emit('connected', {'message': 'Connected to STEEER Visor Backend (Passenger)!'}, room=request.sid)

@socketio.on('disconnect')
def handle_socketio_client_disconnect():
    print(f"[Passenger-SocketIO] Client disconnected (SID: {request.sid})")

if __name__ == '__main__':
    print("[Passenger] Initializing Passenger Service...")
    consumer_thread = threading.Thread(target=rabbitmq_consumer_main_loop, name="RabbitMQConsumerThread")
    consumer_thread.daemon = True
    consumer_thread.start()
    print("[Passenger] RabbitMQ Consumer Thread started.")
    print(f"[Passenger] Starting Flask-SocketIO server on http://0.0.0.0:8080 ...")
    socketio.run(app, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True, debug=False)