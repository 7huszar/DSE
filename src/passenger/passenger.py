from typing import List

from fastapi import FastAPI, Path, Body, status, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging

from passenger_base_models import EmergencyTriggerRequest, EmergencyTriggerResponse, RetrieveLogsResponse, \
    LocationTrackerResponse, HealthResponse

# Constants

LOCATION_TRACKER_URI = 'http://location-tracker-service/'
CENTRAL_DIRECTOR_URI = "http://central-director-service/"

# --- Setup structured logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PassengerAPI")

app = FastAPI(
    title="Passenger API Gateway",
    description="A RESTful api layer that allows to communicate with the backend of the STEEER application.",
    version="1.0.0"
)

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = httpx.AsyncClient(timeout=10)

# This microservice implements the passenger API Gateway

@app.get(
    "/",
    summary="Health check",
    description="Returns a simple message to indicate that the Passenger API gateway is up and running.",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "msg": "Passenger API gateway works!"
                    }
                }
            }
        }
    },
    tags=["Health"],
)
async def get_health() -> HealthResponse:
    """
    Simple health-check endpoint:

    - Returns HTTP 200 with a JSON body confirming service availability.
    """
    return HealthResponse(msg="Passenger API gateway works!")
@app.get("/location_tracker/{vin}")
async def location_tracker(vin: str = Path(
    title="Vehicle Identification Number",
    description="Unique id of vehicle."
)) -> List[LocationTrackerResponse]:
    logger.info(f"Received request for location tracker for VIN {vin}")
    try:
        response = await client.post(LOCATION_TRACKER_URI + "database", json={"vin": vin})
        response.raise_for_status()
        return [LocationTrackerResponse(**loc) for loc in response.json()]
    except httpx.HTTPError as e:
        logger.error(f"Passenger API Gateway error: {str(e)}")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{e}")

@app.get("/central-director/logs",
         summary="Retrieve logs from db.",
         description="Retrieves logs from db up to limit.",
         status_code=status.HTTP_200_OK,
         responses={
             200: {
                 "description": "List of log entries.",
                 "content": {
                     "application/json": {
                         "examples": {
                             "SampleLog": {
                                 "summary": "Example log entry",
                                 "value": {
                                     "src": "distance-monitor-xyz-backend",
                                     "rsn": "Vehicles approaching another object on streets too fast with a frontal distance of 5.01m and a change rate of 7.21m/s.",
                                     "time": "2025-06-05T12:34:56.123456+00:00",
                                     "vin": "4A3AK24FX6E028812"
                                 }
                             }
                         }
                     }
                 }
             }
         }
         )
async def get_central_director_logs() -> List[RetrieveLogsResponse]:

    logger.info("Received GET request for central director logs")

    try:
        response = await client.get(CENTRAL_DIRECTOR_URI + "events")
        response.raise_for_status()
        data = response.json()
        return [RetrieveLogsResponse(**log) for log in data.get("events")]
    except httpx.HTTPError as e:
        logger.error(f"Central Director error: {str(e)}")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{e}")

@app.post(
    "/central-director/emergency/{vin}",
    summary="Trigger an emergency brake.",
    description=("Uses the central director micro service to trigger an emergency brake of the vehicle. "
                 "There are no anticipated errors, since the communication with the vehicle is asynchronous and "
                 "a potential error might not be visible instantly."),
    response_model=EmergencyTriggerResponse,
    status_code=status.HTTP_200_OK,
    responses={
        502: {
            "description": "Failed to forward message to vehicle."
        },
        422: {
            "description": "Validation Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "src"],
                                "msg": "ensure this value has at most 255 characters",
                                "type": "value_error.any_str.max_length"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def trigger_emergency_brake(
        vin: str = Path(
            title="Vehicle Identification Number",
            description="Unique id of vehicle, "
        ),
        body: EmergencyTriggerRequest = Body(
            tile="Emergency Brake Payload",
            description="json object containing source and reason of emergency brake."
        )):

    logger.info(f"Received POST request for central director emergency brake for VIN {vin}")

    try:
        response = await client.post(
            CENTRAL_DIRECTOR_URI + "emergency/" + vin,
            json={
                'src': body.src,
                'rsn': body.rsn
            }
        )
        response.raise_for_status()
        data = response.json()
        return EmergencyTriggerResponse(**data)
    except httpx.HTTPError as e:
        logger.error(f"Passenger API Gateway error: {str(e)}")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{e}")


# --- Main execution block ---
if __name__ == '__main__':
    logger.info("Initializing Passenger API gateway...")