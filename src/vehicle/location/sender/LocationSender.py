from base64 import decode

import pika
import json
import time

connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq-service'))
channel = connection.channel()

channel.exchange_declare(exchange='broker', exchange_type='topic')

payload = {
    'id' : 1,
    'key' : 'BADEAFFE'
}

json_msg = json.dumps(payload).encode('UTF-8')

for i in range(1024):
    channel.basic_publish(
        exchange='broker', routing_key='backend.location.tracker', body=json_msg
    )
    print(json_msg.decode('UTF-8'))
    time.sleep(1)


connection.close()

time.sleep(9999999)