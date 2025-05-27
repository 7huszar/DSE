import threading
import pika
import os
import json
import time
import random
from flask import Flask, request, jsonify
import logging

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


# RabbitMQ connection
credentials = pika.PlainCredentials(
    username=os.environ.get('RABBITMQ_USER', 'guest'),
    password=os.environ.get('RABBITMQ_PASSWORD', 'guest')
)

def get_rabbitmq_connection():
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host='rabbitmq',
            port=int(os.environ.get('RABBITMQ_PORT', 5672)),
            credentials=credentials
        )
    )

# Initialize connection
connection = get_rabbitmq_connection()
channel = connection.channel()
channel.exchange_declare(exchange='broker', exchange_type='topic')

# Simulate vehicle data
vehicle_vin = f"WVWZZZ1JZ3W{random.randint(100000, 999999)}"
lat = 48.2082  # Vienna latitude
lng = 16.3738  # Vienna longitude
speed = 50

def send_location_data():
    global lat, lng, speed, connection, channel
    while True:
        try:
            # Simulate movement
            lat += random.uniform(-0.0001, 0.0001)
            lng += random.uniform(-0.0001, 0.0001)
            speed = max(0, speed + random.uniform(-5, 5))

            data = {
                'vin': vehicle_vin,
                'location': {'lat': lat, 'lng': lng},
                'speed': round(speed, 1),
                'timestamp': time.time(),
                'emergencyBrake': False,
                'frontDistance': random.randint(20, 100),
                'rearDistance': random.randint(20, 100)
            }

            # Send as JSON string
            message = json.dumps(data)

            channel.basic_publish(
                exchange='broker',
                routing_key='backend.location.tracker',
                body=message
            )
            print(f"Sent location data for {vehicle_vin}: lat={lat:.5f}, lng={lng:.5f}, speed={speed:.1f}")
            time.sleep(2)  # Send update every 2 seconds

        except Exception as e:
            print(f"Error sending data: {e}")
            # Try to reconnect
            try:
                connection = get_rabbitmq_connection()
                channel = connection.channel()
                channel.exchange_declare(exchange='broker', exchange_type='topic')
                print("Reconnected to RabbitMQ")
            except:
                print("Failed to reconnect, retrying in 5 seconds...")
                time.sleep(5)

@app.route('/data', methods=['POST'])
def receive_data():
    data = request.get_json()
    logger.info(f"Received data: {str(data)}")

    channel.basic_publish(
        exchange='broker',
        routing_key='backend.location.tracker',
        body=json.dumps(data).encode("utf-8")
    )

    return jsonify({"status": "ok"}), 200

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "vin": vehicle_vin}), 200

if __name__ == '__main__':
    # Start location sender in background
    location_thread = threading.Thread(target=send_location_data)
    location_thread.daemon = True
    location_thread.start()

    # Start Flask app
    app.run(host='0.0.0.0', port=5000)