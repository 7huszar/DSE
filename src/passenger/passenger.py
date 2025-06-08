from typing import List

from fastapi import FastAPI, Request, Path, Body, status, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging

from passenger_base_models import EmergencyTriggerRequest, EmergencyTriggerResponse, RetrieveLogsResponse

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

@app.get("/")
async def getHealth():
    return {"msg": "Passenger API gateway works!"}

@app.get("/location_tracker/{vin}")
async def location_tracker(vin):
    logger.info(f"Received GET request for location tracker for VIN {vin}")
    try:
        response = await client.post(LOCATION_TRACKER_URI + "database", json={"vin": vin})
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Location Tracker error: {str(e)}")
        return {"error": str(e)}

@app.get("/central-director/logs",
         summary="Retrieve logs from db.",
         description="Retrieves logs from db up to limit.",
         status_code=status.HTTP_200_OK,
         )
async def get_central_director_logs(
        limit: int = Query(
        100,
        title="Maximum number of logs",
        description="How many log entries to retrieve (>1)",
        ge=1,
        example=50)) -> List[RetrieveLogsResponse]:

    logger.info(f"Received GET request for central director logs with limit {limit}")

    try:
        response = await client.get(CENTRAL_DIRECTOR_URI + "events")
        response.raise_for_status()
        data = response.json()
        return [RetrieveLogsResponse(**log) for log in data]
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