import os
import time
import pika
import json
import logging
import requests
from pika.exceptions import AMQPConnectionError
from collections import defaultdict

RETRY_WAIT = 5
CONDITION_1_DISTANCE = 20
CONDITION_1_RATE = 3
CONDITION_2_DISTANCE = 40
CONDITION_2_RATE = 5

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

vehicle_distances = defaultdict(lambda: {
    'front_distance': None,
    'last_front_distance': None,
    'last_update_time': None
})

def calculate_change_rate(current_distance, last_distance, time_diff):
    if last_distance is None or time_diff == 0:
        return 0
    return (current_distance - last_distance) / time_diff

def check_emergency_conditions(distance, change_rate):
    if distance < CONDITION_1_DISTANCE and change_rate < -CONDITION_1_RATE:
        return True
    if distance < CONDITION_2_DISTANCE and change_rate < -CONDITION_2_RATE:
        return True
    return False

def vehicle_dm_callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode('utf-8'))
        vin = data.get('vin')
        dst_front = float(data.get('dst_front', 0))
        current_time = time.time()

        logger.info(f"Backend DM received: VIN={vin}, Front={dst_front}m")

        vehicle = vehicle_distances[vin]

        # Calculate change rate
        front_rate = 0
        if vehicle['last_update_time'] is not None:
            time_diff = current_time - vehicle['last_update_time']
            if vehicle['last_front_distance'] is not None:
                front_rate = calculate_change_rate(dst_front, vehicle['last_front_distance'], time_diff)

        # Update stored values
        vehicle['last_front_distance'] = vehicle['front_distance']
        vehicle['front_distance'] = dst_front
        vehicle['last_update_time'] = current_time

        # Send to Central Director via HTTP
        try:
            cd_data = {
                'vin': vin,
                'distance': dst_front,
                'change_rate': front_rate,
                'timestamp': current_time
            }

            response = requests.post(
                'http://central-director-service/distance',
                json=cd_data,
                timeout=5
            )

            if response.status_code == 200:
                logger.info(f"Sent distance data to CD for {vin}")

                # Check if emergency was triggered
                result = response.json()
                if result.get('status') == 'emergency':
                    logger.warning(f"EMERGENCY triggered by CD for {vin}")
                    # The CD will handle the emergency brake

            else:
                logger.error(f"Failed to send to CD: {response.status_code}")

        except Exception as e:
            logger.error(f"Error sending to Central Director: {e}")

        # Also send to passenger for display
        display_data = {
            'vin': vin,
            'frontDistance': dst_front,
            'speed': data.get('speed', 0)
        }
        ch.basic_publish(
            exchange='broker',
            routing_key='backend.location.passenger',
            body=json.dumps(display_data).encode('utf-8')
        )

    except Exception as e:
        logger.error(f"Error processing message: {e}")

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

if __name__ == '__main__':
    # Connect to RabbitMQ
    connection = None
    while connection is None:
        try:
            connection = get_rabbitmq_connection()
            logger.info("Connected to RabbitMQ")
        except AMQPConnectionError as e:
            logger.warning(f"Failed to connect: {e}. Retrying in {RETRY_WAIT} seconds.")
            time.sleep(RETRY_WAIT)

    channel = connection.channel()
    channel.exchange_declare(exchange='broker', exchange_type='topic', durable=True)

    # Create queue for receiving vehicle DM messages
    dm_queue = channel.queue_declare(queue='backend_distance_monitor_queue', durable=True)
    channel.queue_bind(
        exchange='broker',
        queue=dm_queue.method.queue,
        routing_key='backend.location.distance_monitor'
    )

    # Start consuming
    channel.basic_consume(
        queue=dm_queue.method.queue,
        on_message_callback=vehicle_dm_callback,
        auto_ack=True
    )

    logger.info("Backend Distance Monitor started")

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("Stopping Backend Distance Monitor...")
        channel.stop_consuming()
        connection.close()
    except Exception as e:
        logger.error(f"Error: {e}")
        if connection and not connection.is_closed:
            connection.close()