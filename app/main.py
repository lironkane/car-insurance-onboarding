import os
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError


UPSTREAM_URL = os.getenv(
    "UPSTREAM_URL",
    "https://insurance-webhook-945894769129.us-central1.run.app/vehicle-info",
)

app = FastAPI(
    title="Car Insurance Vehicle API",
    version="1.0.0",
)


class VehicleLookupRequest(BaseModel):
    license_plate: str = Field(
        pattern=r"^\d{7,8}$",
        description="Vehicle license plate containing 7 or 8 digits",
    )


class VehicleData(BaseModel):
    license_plate: str
    manufacturer: str
    model: str
    year: int
    color: str


class VehicleSuccessResponse(BaseModel):
    success: bool
    data: VehicleData


def error_response(
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
        },
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/vehicle-info", response_model=VehicleSuccessResponse)
async def vehicle_info(
    request: VehicleLookupRequest,
) -> VehicleSuccessResponse | JSONResponse:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                UPSTREAM_URL,
                json={"license_plate": request.license_plate},
            )
    except httpx.TimeoutException:
        return error_response(
            status_code=504,
            code="UPSTREAM_TIMEOUT",
            message="The vehicle service did not respond in time",
        )
    except httpx.RequestError:
        return error_response(
            status_code=502,
            code="UPSTREAM_UNAVAILABLE",
            message="The vehicle service is currently unavailable",
        )

    if response.status_code == 404:
        return error_response(
            status_code=404,
            code="VEHICLE_NOT_FOUND",
            message="No vehicle was found for this license plate",
        )

    if not response.is_success:
        return error_response(
            status_code=502,
            code="UPSTREAM_ERROR",
            message="The vehicle service returned an unexpected error",
        )

    try:
        payload: Any = response.json()
        return VehicleSuccessResponse.model_validate(payload)
    except (ValueError, ValidationError):
        return error_response(
            status_code=502,
            code="INVALID_UPSTREAM_RESPONSE",
            message="The vehicle service returned an invalid response",
        )
