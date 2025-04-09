import pika, time

credentials = pika.PlainCredentials(username="default_user_ICJsYCAzYCEDta2cePt", password="Zxs3J46nfIVOmzl6RuI474DvWJq0CkVD")
connection = pika.BlockingConnection(pika.ConnectionParameters(host='10.152.183.92', port='5672', credentials=credentials))
channel = connection.channel()

channel.queue_declare(queue='hello')

while(True):
    channel.basic_publish(exchange='',
                          routing_key='hello',
                          body='Hello World!')
    print(" [x] Sent 'Hello World!'")
    #time.sleep(2)

connection.close()