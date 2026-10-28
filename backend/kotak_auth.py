
import os
import secrets
import requests

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

router = APIRouter()


class KotakLoginRequest(BaseModel):
    mobile_number: str = Field(min_length=1)
    ucc: str = Field(min_length=1)
    totp: str = Field(min_length=1)
    mpin: str = Field(min_length=1)


@router.post("/broker/login")
def kotak_login(
    data: KotakLoginRequest,
    access_key: str = Header(
        default="",
        alias="X-Access-Key"
    )
):
    # Check TradeRakshak access key
    expected_key = os.getenv(
        "TRADERAKSHAK_ACCESS_KEY", ""
    )

    if not expected_key or not secrets.compare_digest(
        access_key, expected_key
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    # Check Kotak API token configuration
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

        try:
            result = response.json()
        except ValueError:
            raise HTTPException(
                status_code=502,
                detail="Invalid response from Kotak Neo"
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Kotak login failed"
            )

        login_data = result.get("data", {})
        view_token = login_data.get("token")
        view_sid = login_data.get("sid")

        if not view_token or not view_sid:
            raise HTTPException(
                status_code=502,
                detail="Kotak login session was not returned"
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

        try:
            validate_result = validate_response.json()
        except ValueError:
            raise HTTPException(
                status_code=502,
                detail="Invalid Kotak validation response"
            )

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

        # Do not enable live orders here.
        # This endpoint does not place any orders.
        return {
            "authenticated": True,
            "broker": "Kotak Neo",
            "mode": "test",
            "message": (
                "Authentication response accepted; "
                "live orders remain disabled"
            ),
            "live_orders_enabled": False
        }

    except requests.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Kotak Neo request timed out"
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Could not reach Kotak Neo"
        )
