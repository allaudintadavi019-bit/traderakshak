import os
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class KotakLoginRequest(BaseModel):
    mobile_number: str
    ucc: str
    totp: str
    mpin: str

@router.post("/broker/login")
def kotak_login(data: KotakLoginRequest):
    api_token = os.getenv("KOTAK_API_TOKEN")

    if not api_token:
        raise HTTPException(
            status_code=500,
            detail="Kotak API token is not configured"
        )

    headers = {
        "Authorization": api_token,
        "neo-fin-key": "neotradeapi",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            "https://mis.kotaksecurities.com/login/1.0/tradeApiLogin",
            headers=headers,
            json={
                "mobileNumber": data.mobile_number,
                "ucc": data.ucc,
                "totp": data.totp
            },
            timeout=15
        )

        result = response.json()

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Kotak login failed; check credentials and API response"
            )

        login_data = result.get("data", {})
        view_token = login_data.get("token")
        view_sid = login_data.get("sid")

        if not view_token or not view_sid:
            raise HTTPException(
                status_code=502,
                detail="Kotak did not return a valid login session"
            )

        validate_headers = {
            **headers,
            "sid": view_sid,
            "Auth": view_token
        }

        validate_response = requests.post(
            "https://mis.kotaksecurities.com/login/1.0/tradeApiValidate",
            headers=validate_headers,
            json={"mpin": data.mpin},
            timeout=15
        )

        validate_result = validate_response.json()

        if validate_response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Kotak MPIN validation failed"
            )

        trade_data = validate_result.get("data", {})

        if trade_data.get("status") != "success":
            raise HTTPException(
                status_code=502,
                detail="Kotak authentication was not successful"
            )

        return {
            "authenticated": True,
            "broker": "Kotak Neo",
            "mode": "test",
            "message": "Login successful; no orders were placed"
        }

    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Could not reach Kotak Neo"
        )
