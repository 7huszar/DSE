from fastapi import FastAPI
import httpx
import logging


# Constants

LOCATION_TRACKER_URI = 'http://location-tracker-service/'
CENTRAL_DIRECTOR_URI = "http://central-director-service/"

# --- Setup structured logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PassengerAPI")

app = FastAPI()

client = httpx.AsyncClient(timeout=10)

@app.get("/")
async def getHealth():
    return {"msg": "Passenger API gateway works!"}

@app.get("/location_tracker/{vehicle_vin}")
async def getVehicleLocations(vehicle_vin):
    logger.info(f"Received GET request for location tracker for VIN {vehicle_vin}")
    try:
        response = await client.post(LOCATION_TRACKER_URI + "database", json={"vin": vehicle_vin})
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Location Tracker error: {str(e)}")
        return {"error": str(e)}

@app.get("/central-director/events")
async def getCentralDirectorLog():
    logger.info(f"Received GET request for central director logs")
    try:
        response = await client.get(CENTRAL_DIRECTOR_URI + "events")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Central Director error: {str(e)}")
        return {"error": str(e)}

@app.get("/central-director/emergency/{vin_lower}")
async def triggerEmergencyBrake(vin_lower):
    logger.info(f"Received POST request for central director emergency brake for VIN {vin_lower}")
    try:
        response = await client.post(
            CENTRAL_DIRECTOR_URI + "emergency",
            json={
                'vin': vin_lower,
                'source': 'Frontend Manual Emergency Brake Trigger'
            }
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Central Director error: {str(e)}")
        return {"error": str(e)}


# --- Main execution block ---
if __name__ == '__main__':
    logger.info("Initializing Passenger Service...")