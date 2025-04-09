import threading
import pika
import json
import os
from flask import Flask

app = Flask(__name__)

received_cnt = 0
msg = ''

def callback(ch, method, properties, body):
    global received_cnt
    received_cnt += 1
    global msg
    msg = json.loads(body.decode('UTF-8')).get('key')
    print(f'{str(received_cnt)}, {msg}\n')

def run_consumer():
    credentials = pika.PlainCredentials(username= os.environ['RABBITMQ_USER'], password=os.environ['RABBITMQ_PASSWORD'])
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq', port=os.environ['RABBITMQ_PORT'], credentials=credentials))

    channel = connection.channel()

    channel.exchange_declare(exchange='broker', exchange_type='topic')


    result = channel.queue_declare('', exclusive=False)
    queue_name = result.method.queue

    channel.queue_bind(exchange='broker', queue=queue_name, routing_key='backend.location.tracker')

    channel.basic_consume(
        queue=queue_name, on_message_callback=callback, auto_ack=True)

    channel.start_consuming()

@app.route('/messages')
def check_status():
    global msg
    global received_cnt

    payload = {
        'key' : msg,
        'cnt' : received_cnt
    }
    return json.dumps(payload).encode('UTF-8')

if __name__ == '__main__':
    consumer_thread = threading.Thread(target=run_consumer, daemon=True)
    consumer_thread.start()

    app.run(host='0.0.0.0', port=5000)