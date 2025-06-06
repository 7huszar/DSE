#!/bin/bash

echo "==================== STEEER DEPLOYMENT SCRIPT ===================="
echo "Starting deployment at $(date)"

echo "==================== RUNNING TESTS ===================="
cd ./src/tests/
python3 -m pytest test_vehicle.py test_distance_monitor.py test_central_director.py -v || {
    echo "ERROR: Tests failed! Aborting deployment."
    exit 1
}
cd ../../
echo "Tests passed! Continuing with deployment..."

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
# Build all images
docker build -t localhost:32000/location-tracker:latest ./src/backend/location_tracker/
docker build -t localhost:32000/location-sender:latest -f ./src/vehicle/location_sender/Dockerfile .
docker build -t localhost:32000/data-mock:latest -f ./src/vehicle/data_mock/Dockerfile .
docker build -t localhost:32000/distance-monitor:latest -f ./src/vehicle/distance_monitor/Dockerfile .
docker build -t localhost:32000/passenger:latest ./src/passenger/
docker build -t localhost:32000/visor:latest ./src/frontend/
docker build -t localhost:32000/emergency-brake:latest -f ./src/vehicle/emergency_brake/Dockerfile .
docker build -t localhost:32000/central-director:latest ./src/backend/central_director/
docker build -t localhost:32000/backend-distance-monitor:latest -f ./src/backend/distance_monitor/Dockerfile ./src/backend/distance_monitor/

echo "==================== PUSHING DOCKER IMAGES ===================="
docker push localhost:32000/location-tracker:latest
docker push localhost:32000/location-sender:latest
docker push localhost:32000/data-mock:latest
docker push localhost:32000/passenger:latest
docker push localhost:32000/visor:latest
docker push localhost:32000/distance-monitor:latest
docker push localhost:32000/emergency-brake:latest
docker push localhost:32000/central-director:latest
docker push localhost:32000/backend-distance-monitor:latest

echo "==================== APPLYING CONFIGURATIONS ===================="
# Apply config maps
microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbitmq-configmap.yaml
microk8s kubectl apply -f ./src/backend/location_tracker/location-tracker-configmap.yaml

echo "==================== DEPLOYING DATABASES ===================="
# Deploy PostgreSQL databases
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-postgres-configmap.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-postgres-pv-claim.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-psql-persistant-volume.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-ps-deployment.yaml
microk8s kubectl apply -f ./src/backend/db/location_tracker_db/lt-ps-service.yaml

microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-postgres-configmap.yaml
microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-postgres-pv-claim.yaml
microk8s kubectl apply -f ./src/backend/db/central_director_db/cd-psql-persistant-volume.yaml
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

    # Distance Monitor (per vehicle)
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
microk8s kubectl apply -f ./src/backend/distance_monitor/deployment.yaml

microk8s kubectl apply -f ./src/vehicle/data_mock/deployment.yaml
microk8s kubectl apply -f ./src/vehicle/data_mock/service.yaml

microk8s kubectl apply -f ./src/vehicle/central_director/cd-deployment.yaml

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
    microk8s kubectl rollout restart deployment/distance-monitor-"$VIN_LOWER" 2>/dev/null || true
    microk8s kubectl rollout restart deployment/emergency-brake-"$VIN_LOWER"
done

echo "==================== SETTING UP PORT FORWARDS ===================="
# Setup port forwarding for Grafana
microk8s kubectl port-forward svc/loki-grafana -n monitoring 3000:80 &

# Setup port forwarding for Visor (if using LoadBalancer)
microk8s kubectl port-forward svc/visor-service 8080:80 &

echo "==================== DEPLOYMENT COMPLETE ===================="
echo "Deployment completed at $(date)"
echo ""
echo "Access points:"
echo "- Visor (Frontend): http://localhost:8080"
echo "- Grafana: http://localhost:3000"
echo "  Username: admin"
echo -n "  Password: "
kubectl get secret -n monitoring loki-grafana -o jsonpath="{.data.admin-password}" | base64 --decode
echo ""
echo ""
echo "To check deployment status:"
echo "  microk8s kubectl get pods --all-namespaces"
echo ""
echo "To view logs:"
echo "  microk8s kubectl logs -f deployment/[deployment-name]"