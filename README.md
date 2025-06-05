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

## Configurable Constants

Possible to edit in the respective .yaml files in `{project-route}/configuration/`.

### Data Mock

- `MAX_DST_FRONT`: 50  
  _// TODO_

- `MIN_DST_FRONT`: 0.5  
  _// TODO_

- `MAX_DST_BACK`: 50  
  _// TODO_

- `MIN_DST_BACK`: 0.5  
  _// TODO_

- `SAMPLING_TIME`: 1  
  _// TODO_

- `SCENARIO`: "pedestrian_crossing_road"  
  _// TODO_
### Distance Monitor (Vehicle)

- `FLASK_HOST`: "0.0.0.0"  
  _// TODO_

- `FLASK_PORT`: 5000  
  _// TODO_

- `RETRY_WAIT`: 5
  _// TODO_

### Location Sender

- `FLASK_HOST`: "0.0.0.0"  
  _// TODO_

- `FLASK_PORT`: 5000  
  _// TODO_

- `RETRY_WAIT`: 5
  _// TODO_


## Interfaces

### Data Mock

**Endpoint**
`POST http://data-mock/brake/{vin}`

- `vin`: Vehicle Identification Number in lower case of car

**Description**

Sets the acceleration of the car to `DECELERATION` untile the velocity is 0.0.

**Response** 

```json
{
  "vin": "vin",
  "time": "2025-06-05T12:34:56.123456+00:00"
}  
```
- `time`: UTC ISO 8601 with microseconds
- `vin`: Vehicle Identification Number

### Emergency Brake

**Endpoint**

`POST http://emergency-brake-{vin}/trigger`

- `vin`: Vehicle Identification Number in lower case

**Description**

Triggers emergency break

**Response**

```json
{
  "time": "2025-06-05T12:34:56.123456+00:00"
}
```

- `time`: UTC ISO 8601 with microseconds

**RabbitMq**:

- exchange: `"broker"`

- routing key: `"vehicle.emergency.brake.{vin}"`

**expects**

```json
{
  "time": "2025-06-05T12:34:56.123456+00:00"
}
```

- `time`: UTC ISO 8601 with microseconds

### Location Sender

**Endpoint**

`POST http://location-sender-{vin}/data`

- `vin`: Vehicle Identification Number in lower case

**expects**

```json
{
  "vin": "4A3AK24FX6E028812",
  "time": "2025-06-05T12:34:56.123456+00:00",
  "lon": 16.379584,
  "lat": 48.236819
}
```

- `vin`: Vehicle Identification Number

- `time`: UTC ISO 8601 with microseconds

- `lon`: Longitude as float

- `lat`: Latitude as float

**Description**

Sends received data to backend.

### Distance Monitor (Vehicle)

**Endpoint**

`POST https://distance-monitor-{vin}/data`

**expects**

```json
{
  "vin": "4A3AK24FX6E028812",
  "time": "2025-06-05T12:34:56.123456+00:00",
  "dst_front": 0.0
}
```

- `vin`: Vehicle Identification Number

- `time`: UTC ISO 8601 with microseconds

- `dst_front`: Distance to obstacle in front of vehicle in meter / float

**Description**

Sends data per rabbitmq to Distance Monitor in backend. <br>
If `dst_front` < `MAX_DST_FRONT` it sends a brake request to Emergency Brake.

### Distance Monitor (Backend)

**RabbitMq**

- exchange: `"broker"`

- routing key: `"backend.distance.monitor`

**Expectation**

```json
{
  "vin": "4A3AK24FX6E028812",
  "time": "2025-06-05T12:34:56.123456+00:00",
  "dst_front": 0.0
}
```

- `vin`: Vehicle Identification Number

- `time`: UTC ISO 8601 with microseconds

- `dst_front`: Distance to obstacle in front of vehicle in meter / float

**Description**

_// TODO_

### Location Tracker

**Endpoint**

`GET http://location-tracker/database`

**Description**

Returns ENTIRE content of database.

**Response**

```json
[
  {
    "vin": "4A3AK24FX6E028812",
    "time": "2025-06-05T12:34:56.123456+00:00",
    "lon": 16.379584,
    "lat": 48.236819
  },

  {
    "vin": "1N6SD16S8NC343640",
    "lon": 16.379888,
    "lat": 48.236561,
    "time": "2025-06-05T12:34:56.123456+00:00"
  }
]
```

An array of arbitrary length

- `vin`: Vehicle Identification Number

- `time`: UTC ISO 8601 with microseconds

- `lon`: Longitude as float

- `lat`: Latitude as float

**RabbitMq**:

- exchange: `"broker"`

- routing key: `"backend.location.tracker"`

**Expectation**
```json
{
  "vin": "4A3AK24FX6E028812",
  "time": "2025-06-05T12:34:56.123456+00:00",
  "lon": 16.379584,
  "lat": 48.236819
}
```

**Description**

Saves message in database.

### Central Director

**RabbitMq**:

- exchange: `"broker"`

- routing key: `"backend.central.director"`

**Expectation**

```json
{
  "vin": "4A3AK24FX6E028812",
  "time": "2025-06-05T12:34:56.123456+00:00",
  "src": "distance-monitor-4A3AK24FX6E028812",
  "rsn": "Distance to object in front is 0.5 m < maximal allowed distance 1 m."
}
```

- `vin`: Vehicle Identification Number

- `time`: UTC ISO 8601 with microseconds

- `src`: Any form of identification of service that requested brake (optional)

- `rsn`: Reason for requesting brake (optional)