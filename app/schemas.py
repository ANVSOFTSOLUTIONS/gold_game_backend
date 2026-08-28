from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---- auth ----

class SignupRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    mobile: str = Field(min_length=10, max_length=15)


class RequestOtpRequest(BaseModel):
    mobile: str = Field(min_length=10, max_length=15)


class VerifyOtpRequest(BaseModel):
    mobile: str = Field(min_length=10, max_length=15)
    code: str = Field(min_length=4, max_length=6)


class OtpResponse(BaseModel):
    message: str
    # Only populated when settings.debug=True. In production the code must be
    # sent via a real SMS provider instead of being echoed back in the response.
    dev_otp: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- wallet ----

class WalletOut(BaseModel):
    balance: float
    playable: float
    withdrawable: float
    points: int
    streak: int

    model_config = {"from_attributes": True}


class AddMoneyRequest(BaseModel):
    amount: float = Field(gt=0)


class WithdrawRequest(BaseModel):
    amount: float = Field(gt=0)


class TransactionOut(BaseModel):
    id: int
    type: str
    label: str
    amount: float
    positive: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- game ----

class PlaceBetRequest(BaseModel):
    picks: List[int]
    stake: float = Field(gt=0)

    @field_validator("picks")
    @classmethod
    def validate_picks(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("picks cannot be empty")
        if any(n < 1 or n > 9 for n in v):
            raise ValueError("picks must be between 1 and 9")
        if len(set(v)) != len(v):
            raise ValueError("duplicate picks are not allowed")
        return v


class BetOut(BaseModel):
    id: int
    round_id: int
    picks: List[int]
    stake: float
    total_amount: float
    settled: bool
    won: bool
    payout: float

    model_config = {"from_attributes": True}


class RoundOut(BaseModel):
    id: int
    status: str
    seconds_remaining: int
    drawn_number: Optional[int] = None


class LastDrawsOut(BaseModel):
    draws: List[int]
