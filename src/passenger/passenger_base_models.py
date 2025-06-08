from typing import Optional

from pydantic import BaseModel, Field


class EmergencyTriggerRequest(BaseModel):
    src: Optional[str] = Field(
        title="Trigger Source",
        description=(
            "Identifier for who or what is sending the emergency-brake request."
            "E.g., “Visor Application”."
        ),
        examples=["Visor App"],
        max_length=255
    )
    rsn: Optional[str] = Field(
        title="Reason",
        description="Description of why the emergency brake was triggered.",
        examples=["User triggered emergency brake"],
        max_length=255
    )

class EmergencyTriggerResponse(BaseModel):
    status: str = Field(
        title="status of successful action",
        description="status and what has been done",
        examples=["ok, command sent"]
    ),
    time: str = Field(
        title="Time of execution",
        description="Time of execution in UTC ISO 8601 with microseconds format.",
        examples=["2025-06-05T12:34:56.123456+00:00"]
    )

    class Config:
        schema_extra= {
            "example": {
                "status": "ok, command sent",
                "time": "2025-06-05T12:34:56.123456+00:00"
            }
        }

class RetrieveLogsResponse(BaseModel):
    src: str = Field(
        title="Trigger Source",
        description=(
            "Identifier for who or what is sending the emergency-brake request."
            "E.g., “Visor Application”."
        ),
        examples=["distance-monitor-xyz-backend"],
    ),
    rsn: str = Field(
        title="Reason",
        description="Description of why the emergency brake was triggered.",
        examples=["Vehicles approaching another object on streets too fast with a frontal distance of 5.01m and a "
                  "change rate of 7m/s."]
    ),
    time: str = Field(
        title="timestamp",
        description="Time the emergency brake was executed in UTC ISO 8601 with microseconds format.",
        examples=["2025-06-05T12:34:56.123456+00:00"]
    ),
    vin: str = Field(
        title="Vehicle Identification Number",
        description="Unique id of a vehicle.",
        examples=["4A3AK24FX6E028812"]
    )

class LocationTrackerResponse(BaseModel):
    vin: str = Field(
        title="Vehicle VIN",
        description="Unique identifier of the vehicle.",
        examples=["4A3AK24FX6E028812"]
    )
    latitude: float = Field(
        title="Latitude",
        description="Last known latitude in decimal degrees.",
        examples=["48.236653"]
    )
    longitude: float = Field(
        title="Longitude",
        description="Last known longitude in decimal degrees.",
        examples=["16.379773"]
    )
    timestamp: str = Field(
        title="Timestamp",
        description="UTC ISO-8601 with microseconds timestamp of when the location was recorded.",
        examples=["2025-06-05T12:34:56.123456+00:00"]
    )

class HealthResponse(BaseModel):
    msg: str = Field(
        title="Health message",
        description="Indicates that the Passenger API gateway is running.",
        examples=["Passenger API gateway works!"]
    )