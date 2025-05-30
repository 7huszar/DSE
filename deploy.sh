echo "apply plugins"
microk8s kubectl apply -f "https://github.com/rabbitmq/cluster-operator/releases/latest/download/cluster-operator.yml"

microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbit_mq.yaml
microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbitmq-configmap.yaml

microk8s helm3 repo add grafana https://grafana.github.io/helm-charts
microk8s helm3 install loki grafana/loki-stack --set grafana.enabled=true,fluent-bit.enabled=true,promtail.enabled=false --set fluent-bit.inputTail.Mem_Buf_Limit=50MB -n monitoring --create-namespace

microk8s helm3 upgrade loki grafana/loki-stack \
  --set grafana.enabled=true \
  --set fluent-bit.enabled=true \
  --set promtail.enabled=false \
  --set fluent-bit.inputTail.Mem_Buf_Limit=200MB \
  -n monitoring

echo "build docker images"
docker build -t localhost:32000/location-tracker:latest ./src/backend/location_tracker/
docker build -t localhost:32000/location-sender:latest ./src/vehicle/location_sender/
docker build -t localhost:32000/data-mock:latest ./src/vehicle/data_mock/
docker build -t localhost:32000/passenger:latest ./src/passenger/
docker build -t localhost:32000/visor:latest ./src/frontend/

echo "push docker images into microk8s registry"
docker push localhost:32000/location-tracker:latest
docker push localhost:32000/location-sender:latest
docker push localhost:32000/data-mock:latest
docker push localhost:32000/passenger:latest
docker push localhost:32000/visor:latest


jq -c '.[]' ./src/vehicle/data_mock/vehicles.json | while read -r record; do

  VIN=$(echo "$record" | jq -r '.vin')
  VIN_LOWER=${VIN,,}
  export VIN_LOWER

  echo "deploy services for vehicle with vin: $VIN as location_sender-$VIN_LOWER"


  envsubst < ./src/vehicle/location_sender/deployment.yaml | microk8s kubectl apply -f -

  envsubst < ./src/vehicle/location_sender/service.yaml | microk8s kubectl apply -f -

  microk8s kubectl rollout restart deployment/location-sender-"$VIN_LOWER"


done

microk8s kubectl apply -f ./configuration/data_mock_config.yaml

echo "apply deployment files"
microk8s kubectl apply -f ./src/backend/location_tracker/deployment.yaml
microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbit_mq.yaml
microk8s kubectl apply -f ./src/vehicle/data_mock/deployment.yaml
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
microk8s kubectl apply -f ./src/backend/rabbit_mq/rabbitmq-configmap.yaml
microk8s kubectl apply -f ./src/backend/location_tracker/location-tracker-configmap.yaml

echo "apply service files"
microk8s kubectl apply -f ./src/backend/location_tracker/service.yaml
microk8s kubectl apply -f ./src/broker/service.yaml
microk8s kubectl apply -f ./src/vehicle/data_mock/service.yaml

echo "restart self made application"
microk8s kubectl rollout restart deployment/location-tracker
microk8s kubectl rollout restart deployment/data-mock
microk8s kubectl rollout restart deployment/passenger
microk8s kubectl rollout restart deployment/visor
microk8s kubectl rollout restart deployment/lt-postgres
microk8s kubectl rollout restart deployment/cd-postgres

microk8s kubectl port-forward svc/loki-grafana -n monitoring 3000:80 &