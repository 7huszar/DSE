import pika, time, os

credentials = pika.PlainCredentials(username= os.environ['RABBITMQ_USER'], password=os.environ['RABBITMQ_PASSWORD'])
connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.environ['RABBITMQ_HOST'], port=os.environ['RABBITMQ_PORT'], credentials=credentials))
channel = connection.channel()

channel.queue_declare(queue='hello')

while(True):
    channel.basic_publish(exchange='',
                          routing_key='hello',
                          body='Hello World!')
    print(" [x] Sent 'Hello World!'")
    time.sleep(2)