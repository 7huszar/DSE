from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pika
import json
import threading
import os

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# RabbitMQ connection
credentials = pika.PlainCredentials(
    username=os.environ.get('RABBITMQ_USER', 'guest'),
    password=os.environ.get('RABBITMQ_PASSWORD', 'guest')
)

vehicles = {}  # Store vehicle data in memory

def connect_rabbitmq():
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='rabbitmq',
                port=int(os.environ.get('RABBITMQ_PORT', 5672)),
                credentials=credentials
            )
        )
        channel = connection.channel()
        channel.exchange_declare(exchange='broker', exchange_type='topic')

        # Subscribe to location updates
        result = channel.queue_declare('', exclusive=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange='broker', queue=queue_name, routing_key='backend.location.#')

        def callback(ch, method, properties, body):
            data = json.loads(body)
            update_vehicle_data(data)

        channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
        print("Connected to RabbitMQ, listening for vehicle updates...")
        channel.start_consuming()
    except Exception as e:
        print(f"RabbitMQ connection error: {e}")
        # Retry connection after 5 seconds
        threading.Timer(5.0, connect_rabbitmq).start()

def update_vehicle_data(data):
    vin = data.get('vin')
    if vin:
        vehicles[vin] = data
        # Emit update to connected clients
        socketio.emit('vehicle_update', {'type': 'vehicle_update', 'vehicle': data})

@app.route('/vehicles', methods=['GET'])
def get_vehicles():
    return jsonify(list(vehicles.values()))

@app.route('/vehicle/<vin>', methods=['GET'])
def get_vehicle(vin):
    vehicle = vehicles.get(vin)
    if vehicle:
        return jsonify(vehicle)
    return jsonify({'error': 'Vehicle not found'}), 404

@socketio.on('connect')
def handle_connect():
    emit('connected', {'data': 'Connected to STEEER backend'})

if __name__ == '__main__':
    # Start RabbitMQ consumer in background thread
    rabbitmq_thread = threading.Thread(target=connect_rabbitmq)
    rabbitmq_thread.daemon = True
    rabbitmq_thread.start()

    socketio.run(app, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True)