import threading

import pika
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

credentials = pika.PlainCredentials(username= os.environ['RABBITMQ_USER'], password=os.environ['RABBITMQ_PASSWORD'])
connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq', port=os.environ['RABBITMQ_PORT'], credentials=credentials))
channel = connection.channel()

channel.exchange_declare(exchange='broker', exchange_type='topic')

def send_data(data):

    channel.basic_publish(
        exchange='broker', routing_key='backend.location.tracker', body=data
    )
    print("sent")

@app.route('/data', methods=['POST'])
def receive_data():
    data = request.get_json()
    pass_on = threading.Thread(target=send_data(jsonify(data)))
    pass_on.start()

    return '', 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)