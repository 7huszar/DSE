echo "apply plugins"
microk8s kubectl apply -f "https://github.com/rabbitmq/cluster-operator/releases/latest/download/cluster-operator.yml"

microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbit_mq.yaml
microk8s kubectl apply -f ./src/backend/rabbitmq-configmap.yaml

echo "build docker images"
docker build -t localhost:32000/location-tracker:latest ./src/backend/location_tracker/
docker build -t localhost:32000/location-sender:latest ./src/vehicle/location_sender/
docker build -t localhost:32000/data-mock:latest ./src/vehicle/data_mock/

echo "push docker images into microk8s registry"
docker push localhost:32000/location-tracker:latest
docker push localhost:32000/location-sender:latest
docker push localhost:32000/data-mock:latest

echo "apply deployment files"
microk8s kubectl apply -f ./src/backend/location_tracker/deployment.yaml
microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbit_mq.yaml
microk8s kubectl apply -f ./src/vehicle/data_mock/deployment.yaml

echo "apply configmaps"
microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbitmq-configmap.yaml
microk8s kubectl apply -f ./src/backend/location_tracker/location-tracker-configmap.yaml


echo "apply service files"
microk8s kubectl apply -f ./src/backend/location_tracker/service.yaml
microk8s kubectl apply -f ./src/broker/service.yaml
microk8s kubectl apply -f ./src/vehicle/data_mock/service.yaml

echo "restart self made application"
microk8s kubectl rollout restart deployment/location-tracker
microk8s kubectl rollout restart deployment/location-sender
microk8s kubectl rollout restart deployment/data-mock