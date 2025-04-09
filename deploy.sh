echo "apply plugins"
microk8s kubectl apply -f "https://github.com/rabbitmq/cluster-operator/releases/latest/download/cluster-operator.yml"

echo "build docker images"
docker build -t localhost:32000/location-tracker:latest ./src/backend_location/tracker/
docker build -t localhost:32000/location-sender:latest ./src/vehicle_location/sender/

echo "push docker images into microk8s registry"
docker push localhost:32000/location-tracker:latest
docker push localhost:32000/location-sender:latest

echo "apply deployment files"
microk8s kubectl apply -f ./src/backend/location_tracker/deployment.yaml
microk8s kubectl apply -f ./src/vehicle/location_sender/deployment.yaml
microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbit_mq.yaml

echo "apply configmaps"
microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbitmq-configmap.yaml


echo "apply service files"
microk8s kubectl apply -f ./src/backend/location_tracker/service.yaml
microk8s kubectl apply -f ./src/vehicle/location_sender/service.yaml
microk8s kubectl apply -f ./src/broker/service.yaml

echo "restart self made application"
microk8s kubectl rollout restart deployment/location-tracker
microk8s kubectl rollout restart deployment/location-sender