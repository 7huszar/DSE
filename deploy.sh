echo "build docker images"
docker build -t localhost:32000/hello-world-app:latest ./src/backend/hello/world/
docker build -t localhost:32000/location-tracker:latest ./src/backend/location/tracker/
docker build -t localhost:32000/location-sender:latest ./src/vehicle/location/sender/

# echo "pull docker images"
# docker pull rabbitmq


echo "push docker images into microk8s registry"
docker push localhost:32000/hello-world-app:latest
docker push localhost:32000/location-tracker:latest
docker push localhost:32000/location-sender:latest

echo "apply deployment files"
microk8s kubectl apply -f ./src/backend/hello/world/deployment.yaml
microk8s kubectl apply -f ./src/backend/location/tracker/deployment.yaml
microk8s kubectl apply -f ./src/vehicle/location/sender/deployment.yaml
microk8s kubectl apply -f ./src/broker/deployment.yaml


echo "apply service files"
microk8s kubectl apply -f ./src/backend/hello/world/service.yaml
microk8s kubectl apply -f ./src/backend/location/tracker/service.yaml
microk8s kubectl apply -f ./src/vehicle/location/sender/service.yaml
microk8s kubectl apply -f ./src/broker/service.yaml

echo "restart self made application"
microk8s kubectl rollout restart deployment/hello-world
microk8s kubectl rollout restart deployment/location-tracker
microk8s kubectl rollout restart deployment/location-sender