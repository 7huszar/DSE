#!/bin/bash

echo "==================== CLEANING UP OLD PROCESSES ===================="
pkill -f "kubectl port-forward svc/loki-grafana -n monitoring 3000:80" \
  || echo "No old loki-grafana port-forward to clean up"

# Kill old visor-service forward
pkill -f "kubectl port-forward svc/visor-service 8080:80" \
  || echo "No old visor-service port-forward to clean up"

echo "==================== STEEER DEPLOYMENT SCRIPT ===================="
echo "Starting deployment at $(date)"

#echo "==================== RUNNING TESTS ===================="
#python3 -m pytest src/tests/ -v || {
#    echo "ERROR: Tests failed! Aborting deployment."
#    exit 1
#}
#echo "Tests passed! Continuing with deployment..."

echo "==================== ENABLING PLUGINS ===================="
microk8s enable helm3
microk8s enable dashboard
microk8s enable registry
microk8s enable dns
microk8s enable storage

echo "==================== APPLYING PLUGINS ===================="
microk8s kubectl apply -f "https://github.com/rabbitmq/cluster-operator/releases/latest/download/cluster-operator.yml"

# Setup monitoring
echo "==================== SETTING UP MONITORING ===================="
microk8s helm3 repo add grafana https://grafana.github.io/helm-charts
microk8s helm3 install loki grafana/loki-stack \
  --set grafana.enabled=true \
  --set fluent-bit.enabled=true \
  --set promtail.enabled=false \
  --set fluent-bit.inputTail.Mem_Buf_Limit=200MB \
  -n monitoring

echo "==================== BUILDING DOCKER IMAGES ===================="
docker build -t localhost:32000/location-tracker:latest ./src/backend/location_tracker/
docker build -t localhost:32000/location-sender:latest -f ./src/vehicle/location_sender/Dockerfile .
docker build -t localhost:32000/data-mock:latest -f ./src/vehicle/data_mock/Dockerfile .
docker build -t localhost:32000/distance-monitor:latest -f ./src/vehicle/distance_monitor/Dockerfile .
docker build -t localhost:32000/passenger:latest ./src/passenger/
docker build -t localhost:32000/visor:latest ./src/frontend/
docker build -t localhost:32000/emergency-brake:latest -f ./src/vehicle/emergency_brake/Dockerfile .
docker build -t localhost:32000/central-director:latest ./src/backend/central_director/
docker build -t localhost:32000/bridge:latest ./src/frontend/bridge/

echo "==================== PUSHING DOCKER IMAGES ===================="
docker push localhost:32000/location-tracker:latest
docker push localhost:32000/location-sender:latest
docker push localhost:32000/data-mock:latest
docker push localhost:32000/passenger:latest
docker push localhost:32000/visor:latest
docker push localhost:32000/distance-monitor:latest
docker push localhost:32000/emergency-brake:latest
docker push localhost:32000/central-director:latest
docker push localhost:32000/bridge:latest

echo "==================== APPLYING CONFIGURATIONS ===================="
microk8s kubectl apply -f ./configuration/data_mock_config.yaml
microk8s kubectl apply -f ./configuration/broker_topic_config.yaml
microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbitmq-configmap.yaml
microk8s kubectl apply -f ./src/backend/location_tracker/location-tracker-configmap.yaml

echo "==================== DEPLOYING DATABASES ===================="
# Location Tracker DB
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-psql-persistant-volume.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-postgres-pv-claim.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-postgres-configmap.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-ps-deployment.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-ps-service.yaml

# Central Director DB
microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-psql-persistant-volume.yaml
microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-postgres-pv-claim.yaml
microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-postgres-configmap.yaml
microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-ps-deployment.yaml
microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-ps-service.yaml

# Wait for databases to be ready
echo "Waiting for databases to be ready..."
# sleep 20

echo "==================== DEPLOYING VEHICLE SERVICES ===================="
# Deploy location senders for each vehicle
jq -c '.[]' vehicles.json | while read -r record; do
    VIN=$(echo "$record" | jq -r '.vin')
    VIN_LOWER=${VIN,,}
    export VIN_LOWER
    export VIN

    echo "Deploying services for vehicle with VIN: $VIN as location-sender-$VIN_LOWER"

    # Location Sender
    envsubst < ./src/vehicle/location_sender/deployment.yaml | microk8s kubectl apply -f -
    envsubst < ./src/vehicle/location_sender/service.yaml | microk8s kubectl apply -f -

    echo "Deploying distance monitors for vehicle side..."
    SERVICE_DEPLOYMENT_LOCATION="vehicle"
    export SERVICE_DEPLOYMENT_LOCATION
    echo $SERVICE_DEPLOYMENT_LOCATION

    # Distance Monitor (on Vehicle)
    envsubst < ./src/vehicle/distance_monitor/deployment.yaml | microk8s kubectl apply -f -
    envsubst < ./src/vehicle/distance_monitor/service.yaml | microk8s kubectl apply -f -

    echo "Deploying distance monitor for backend side..."
    SERVICE_DEPLOYMENT_LOCATION="backend"
    export SERVICE_DEPLOYMENT_LOCATION
    echo $SERVICE_DEPLOYMENT_LOCATION

    # Distance Monitor (in Backend)
    envsubst < ./src/vehicle/distance_monitor/deployment.yaml | microk8s kubectl apply -f -
    envsubst < ./src/vehicle/distance_monitor/service.yaml | microk8s kubectl apply -f -

    envsubst < ./src/vehicle/emergency_brake/deployment.yaml | microk8s kubectl apply -f -
    envsubst < ./src/vehicle/emergency_brake/service.yaml | microk8s kubectl apply -f -

done

echo "==================== DEPLOYING CORE SERVICES ===================="
# Deploy core services
microk8s kubectl apply -f ./configuration/

echo "apply deployment files"
microk8s kubectl apply -f ./src/backend/location_tracker/deployment.yaml
microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbit_mq.yaml

microk8s kubectl apply -f ./src/vehicle/data_mock/deployment.yaml
microk8s kubectl apply -f ./src/vehicle/data_mock/service.yaml

microk8s kubectl apply -f ./src/backend/central_director/cd-deployment.yaml
microk8s kubectl apply -f ./src/backend/central_director/service.yaml

microk8s kubectl apply -f ./src/passenger/deployment.yaml
microk8s kubectl apply -f ./src/frontend/deployment.yaml

echo "postgres db files"

microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-postgres-configmap.yaml
microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-postgres-pv-claim.yaml
microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-psql-persistant-volume.yaml
microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-ps-deployment.yaml
microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-ps-service.yaml

microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-postgres-configmap.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-postgres-pv-claim.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-psql-persistant-volume.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-ps-deployment.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-ps-service.yaml

echo "apply configmaps"
microk8s kubectl apply -f ./src/backend/location_tracker/location-tracker-configmap.yaml

echo "apply service files"
microk8s kubectl apply -f ./src/backend/location_tracker/service.yaml

echo "==================== RESTARTING DEPLOYMENTS ===================="
# Restart all deployments to ensure latest images
microk8s kubectl rollout restart deployment/location-tracker
microk8s kubectl rollout restart deployment/data-mock
microk8s kubectl rollout restart deployment/passenger
microk8s kubectl rollout restart deployment/visor
microk8s kubectl rollout restart deployment/central-director

# Restart vehicle-specific deployments
jq -c '.[]' vehicles.json | while read -r record; do
    VIN=$(echo "$record" | jq -r '.vin')
    VIN_LOWER=${VIN,,}
    microk8s kubectl rollout restart deployment/location-sender-"$VIN_LOWER"
    microk8s kubectl rollout restart deployment/distance-monitor-"$VIN_LOWER"-vehicle 2>/dev/null || true
    microk8s kubectl rollout restart deployment/distance-monitor-"$VIN_LOWER"-backend 2>/dev/null || true
    microk8s kubectl rollout restart deployment/emergency-brake-"$VIN_LOWER"
done

echo "==================== WAITING FOR DEPLOYMENTS TO BE READY ===================="
microk8s kubectl wait --for=condition=available --timeout=300s deployment/visor
echo "Giving the cluster a moment to stabilize..."
sleep 5

echo "==================== SETTING UP PORT FORWARDS ===================="
# Setup port forwarding for Grafana in the background
microk8s kubectl port-forward svc/loki-grafana -n monitoring 3000:80 &

# The final command will run in the foreground, keeping the script and the connection alive.
echo "==================== DEPLOYMENT COMPLETE ===================="
echo ""
echo "Access points:"
echo "- Visor (Frontend): http://localhost:8080"
echo "- Grafana: http://localhost:3000"
echo "  (Use a separate terminal to get the Grafana password if needed via 'kubectl get secret ...')"
echo ""
microk8s kubectl port-forward svc/visor-service 8080:80 &