How to start rabbit/consumer/producer:

- kubectl apply -f rabbit_mq.yaml
- cd consumer
- docker build -t localhost:32000/consumer:latest
- docker tag <docker image ls image id> localhost:32000/consumer:latest
- docker push localhost:32000/consumer:latest
- kubectl apply -f consumer.yaml
- cd ..
- cd producer
- docker build -t localhost:32000/producer:latest
- docker tag <docker image ls image id> localhost:32000/producer:latest
- docker push localhost:32000/producer:latest
- kubectl apply -f producer.yaml


RabbitMQ Dashboard:

- kubectl port-forward -n default <rabbitmq service name> 8080:15672
- User: default_user_ICJsYCAzYCEDta2cePt
- Password: Zxs3J46nfIVOmzl6RuI474DvWJq0CkVD