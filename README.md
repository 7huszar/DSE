# Welcome to our nice little DSE project

https://microk8s.io/#install-microk8s

## Dashboard

microk8s enable dashboard

microk8s dashboard-proxy

## Deployment:

Before you deploy, you need to enable the registry of Microk8s:

microk8s enable registry

- docker build -t localhost:32000/hello-world-app:latest .

- sudo docker push localhost:32000/hello-world-app:latest

- sudo microk8s kubectl apply -f deployment.yaml

- sudo microk8s kubectl apply -f service.yaml 
