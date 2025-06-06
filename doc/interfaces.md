## Interfaces

### Data Mock

**Endpoint**
`POST http://data-mock/brake/{vin}`

- `vin`: Vehicle Identification Number in lower case of vehicle

**Description**

Sets the acceleration of the car to `DECELERATION` untile the velocity is 0.0.

**Response**

```json
{
  "vin": "vin",
  "time": "2025-06-05T12:34:56.123456+00:00"
}  
```
- `time`: _UTC ISO 8601 with microseconds_, start time of emergency brake
- `vin`: _Vehicle Identification Number_, vehicle that executes emergency brake

**Endpoint**
`POST http://data-mock/scenario/{scenario}`

- `scenario` valid scenario name

**Description**

Starts the scenario with the scenario name

**Response**

- `OK 200` scenario started

- `NOT FOUND 404` if unknown scenario

### Emergency Brake

**Endpoint**

`POST http://emergency-brake-{vin}/trigger`

- `vin`: _Vehicle Identification Number in lower case_

**Description**

Triggers emergency break, Sends a message to Central Director of emergency brake triggered.

**Expectation**

```json
{
  "time": "2025-06-05T12:34:56.123456+00:00",
  "src": "Central Director",
  "rsn": "triggered by user"
}
```

**Response**

- `OK 200` emergency brake triggered
- `CONFLICT 409` if emergency brake was already triggered

**RabbitMq**:

- Exchange: `"broker"`

- Routing Key: `"vehicle.{vin}.emergency.brake"`

**expects**

```json
{
  "time": "2025-06-05T12:34:56.123456+00:00",
  "src": "Central Director",
  "rsn": "triggered by user"
}
```

- `time`: _UTC ISO 8601 with microseconds_, time of request

**Description**

Triggers emergency break, Sends a message to Central Director of emergency brake triggered.

### Location Sender

**Endpoint**

`POST http://location-sender-{vin}/data`

- `vin`: _Vehicle Identification Number in lower case_

**expects**

```json
{
  "vin": "4A3AK24FX6E028812",
  "time": "2025-06-05T12:34:56.123456+00:00",
  "lon": 16.379584,
  "lat": 48.236819
}
```

- `vin`: _Vehicle Identification Number_

- `time`: _UTC ISO 8601 with microseconds_

- `lon`: _Longitude as float_

- `lat`: _Latitude as float_

**Description**

Sends received data to backend.

### Distance Monitor (Vehicle)

**Endpoint**

`POST https://distance-monitor-{vin}/data`

- `vin`: _Vehicle Identification Number in lower case_

**expects**

```json
{
  "vin": "4A3AK24FX6E028812",
  "time": "2025-06-05T12:34:56.123456+00:00",
  "dst_front": 0.0
}
```

- `vin`: _Vehicle Identification Number_

- `time`: _UTC ISO 8601 with microseconds_ snapshot time of data

- `dst_front`: _distance in meters_, _float_ Distance to obstacle in front of vehicle

**Description**

Sends data per rabbitmq to Distance Monitor in backend. <br>
If `dst_front` < `MAX_DST_FRONT` it sends a brake request to Emergency Brake.

### Distance Monitor (Backend)

**RabbitMq**

- exchange: `"broker"`

- routing key: `"backend.{vin}.distance.monitor`

**Expectation**

```json
{
  "vin": "4A3AK24FX6E028812",
  "time": "2025-06-05T12:34:56.123456+00:00",
  "dst_front": 0.0
}
```

- `vin`: _Vehicle Identification Number_

- `time`: _UTC ISO 8601 with microseconds_ snaphsot time of data

- `dst_front`: _distance in meters_, _float_ Distance to obstacle in front of vehicle

**Description**

_// TODO_

### Location Tracker

**Endpoint**

`GET http://location-tracker/database?limit=1&vin=4A3AK24FX6E028812&start=2024-06-05T12:34:56.123456+00:00&end=2025-06-05T12:34:56.123456+00:00`

Request Parameters:
- limit: Optional, number, Limit the amount of data points
- vin: Optional, String, filters for vehicle vin
- start: Optional, UTC ISO 8601 with microseconds, filter for start date
- end: Optional, UTC ISO 8601 with microseconds, filter for end date


**Description**

Returns content of database.

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
  "rsn": "Distance to object in front is 0.5 m < maximal allowed distance 1 m.",
  "status": "triggered"
}
```

- `vin`: Vehicle Identification Number

- `time`: UTC ISO 8601 with microseconds

- `src`: Any form of identification of service that requested brake (optional)

- `rsn`: Reason for requesting brake (optional)

- `status`: `triggered` if the emergency brake just triggered and `complete` if the car stands still

**Endpoint**

`POST http://central-director/brake/{vin}`

- `vin` Vehicle Identification Number

**Response**

- `OK 200` requested brake

- `CONFLICT 409` emergency brake in progress

**Endpoint**

`GET http://central-director/brakes?limit=1&vin=4A3AK24FX6E028812&start=2024-06-05T12:34:56.123456+00:00&end=2025-06-05T12:34:56.123456+00:00`

- `limit`: Optional, number, Limit the amount of data points

- `vin`: Optional, String, filters for vehicle vin

- `start`: Optional, UTC ISO 8601 with microseconds, filter for start date

- `end`: Optional, UTC ISO 8601 with microseconds, filter for end date
