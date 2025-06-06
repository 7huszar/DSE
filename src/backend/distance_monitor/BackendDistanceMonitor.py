import os
import time
import pika
import json
import logging
import requests
from pika.exceptions import AMQPConnectionError
from collections import defaultdict

# --- Constants ---
RETRY_WAIT = 5

# --- Logging Setup ---
# Set the logging level to INFO. Use DEBUG for more verbose output.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BackendDistanceMonitor")

# --- In-memory state for calculations ---
vehicle_distances = defaultdict(lambda: {
    'front_distance': None,
    'last_front_distance': None,
    'last_update_time': None
})

def calculate_change_rate(current_distance, last_distance, time_diff):
    if last_distance is None or time_diff == 0:
        return 0
    return (current_distance - last_distance) / time_diff

# The logic in this service is to forward data, not to check conditions itself.
# The Central Director is responsible for checking conditions.
# def check_emergency_conditions(...) -> This function is removed as it's not used here.

# This callback processes messages from the vehicle's distance monitor service.
def vehicle_dm_callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode('utf-8'))
        vin = data.get('vin')
        dst_front = float(data.get('dst_front', 0))
        current_time = time.time()

        if not vin:
            logger.warning("Received message without VIN, discarding.")
            return

        logger.debug(f"Backend DM received: VIN={vin}, Front={dst_front:.2f}m")
        vehicle = vehicle_distances[vin]

        # Calculate the rate of distance change
        front_rate = 0
        if vehicle['last_update_time'] and vehicle['last_front_distance']:
            time_diff = current_time - vehicle['last_update_time']
            front_rate = calculate_change_rate(dst_front, vehicle['last_front_distance'], time_diff)

        # Update the state for the next calculation
        vehicle['last_front_distance'] = vehicle['front_distance']
        vehicle['front_distance'] = dst_front
        vehicle['last_update_time'] = current_time

        # --- Forward processed data to Central Director via HTTP ---
        try:
            cd_data = {'vin': vin, 'distance': dst_front, 'change_rate': front_rate}
            cd_url = 'http://central-director-service/distance'
            response = requests.post(cd_url, json=cd_data, timeout=5)

            if response.status_code == 200:
                logger.info(f"Forwarded data for {vin} to CD. Response: {response.json().get('status')}")
            else:
                logger.error(f"Failed to send data to CD for {vin}. Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending data to Central Director: {e}")

        # --- Forward raw data to Passenger for real-time Visor display ---
        display_data = {'vin': vin, 'frontDistance': dst_front, 'speed': data.get('speed', 0)}
        ch.basic_publish(
            exchange='broker',
            routing_key='backend.location.passenger',
            body=json.dumps(display_data).encode('utf-8')
        )

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"Error processing message due to invalid format: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred in the callback: {e}", exc_info=True)

def get_rabbitmq_connection():
    credentials = pika.PlainCredentials(
        username=os.environ.get('RABBITMQ_USER', 'guest'),
        password=os.environ.get('RABBITMQ_PASSWORD', 'guest')
    )
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.environ.get('RABBITMQ_HOST', 'rabbitmq'),
            port=int(os.environ.get('RABBITMQ_PORT', 5672)),
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
    )

# The main block now includes a robust reconnect loop.
if __name__ == '__main__':
    logger.info("Backend Distance Monitor Service is starting...")
    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            logger.info("Successfully connected to RabbitMQ.")

            channel.exchange_declare(exchange='broker', exchange_type='topic', durable=True)
            dm_queue = channel.queue_declare(queue='backend_distance_monitor_queue', durable=True)
            channel.queue_bind(
                exchange='broker',
                queue=dm_queue.method.queue,
                routing_key='backend.location.distance_monitor'
            )
            # Use auto_ack=True for simplicity, as per the original code.
            channel.basic_consume(
                queue=dm_queue.method.queue,
                on_message_callback=vehicle_dm_callback,
                auto_ack=True
            )
            logger.info("Consumer started. Waiting for messages...")
            channel.start_consuming()
        except AMQPConnectionError as e:
            logger.warning(f"Connection to RabbitMQ failed: {e}. Retrying in {RETRY_WAIT} seconds.")
        except KeyboardInterrupt:
            logger.info("Shutdown signal received. Stopping service.")
            if 'connection' in locals() and connection.is_open:
                connection.close()
            break # Exit the while loop
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)

        time.sleep(RETRY_WAIT)