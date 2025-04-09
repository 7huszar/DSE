from base64 import decode

import pika
import json
import time
import os

credentials = pika.PlainCredentials(username= os.environ['RABBITMQ_USER'], password=os.environ['RABBITMQ_PASSWORD'])
connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq', port=os.environ['RABBITMQ_PORT'], credentials=credentials))
channel = connection.channel()

channel.exchange_declare(exchange='broker', exchange_type='topic')


payload = {
    'id' : 1,
    'key' : 'BADEAFFE'
}

json_msg = json.dumps(payload).encode('UTF-8')

while True:
    channel.basic_publish(
        exchange='broker', routing_key='backend.location.tracker', body=json_msg
    )
    print(json_msg.decode('UTF-8'))
    time.sleep(1)

