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

## Logs:

- make sure ```microk8s enable helm3 ```

- run ./deploy.sh

- call http://localhost:3000

- user is "admin" and you can retrieve pwd with:
``` kubectl get secret -n monitoring loki-grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo ```
