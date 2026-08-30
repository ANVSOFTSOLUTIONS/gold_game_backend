from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from .. import schemas, security
from ..config import settings
from ..deps import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.OtpResponse)
def signup(payload: schemas.SignupRequest, db: Database = Depends(get_db)):
    existing = db.users.find_one({"mobile": payload.mobile})
    if existing and existing["is_verified"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Mobile number already registered")

    if not existing:
        result = db.users.insert_one(
            {
                "full_name": payload.full_name,
                "mobile": payload.mobile,
                "is_verified": False,
                "created_at": datetime.utcnow(),
            }
        )
        db.wallets.insert_one(
            {
                "user_id": result.inserted_id,
                "balance": 0.0,
                "playable": 0.0,
                "withdrawable": 0.0,
                "points": 0,
                "streak": 0,
            }
        )

    return _issue_otp(db, payload.mobile, purpose="signup")


@router.post("/request-otp", response_model=schemas.OtpResponse)
def request_otp(payload: schemas.RequestOtpRequest, db: Database = Depends(get_db)):
    user = db.users.find_one({"mobile": payload.mobile})
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account with this mobile number")
    return _issue_otp(db, payload.mobile, purpose="login")


@router.post("/verify-otp", response_model=schemas.TokenResponse)
def verify_otp(payload: schemas.VerifyOtpRequest, db: Database = Depends(get_db)):
    otp = db.otp_codes.find_one(
        {"mobile": payload.mobile, "consumed": False},
        sort=[("_id", -1)],
    )
    if not otp or otp["expires_at"] < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OTP expired or not found, please request a new one")
    if otp["attempts"] >= 5:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, request a new OTP")

    db.otp_codes.update_one({"_id": otp["_id"]}, {"$inc": {"attempts": 1}})

    if not security.verify_otp_hash(payload.code, otp["code_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect OTP")

    db.otp_codes.update_one({"_id": otp["_id"]}, {"$set": {"consumed": True}})

    user = db.users.find_one({"mobile": payload.mobile})
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    db.users.update_one({"_id": user["_id"]}, {"$set": {"is_verified": True}})

    token = security.create_access_token(str(user["_id"]), user["mobile"])
    return schemas.TokenResponse(access_token=token)


def _issue_otp(db: Database, mobile: str, purpose: str) -> schemas.OtpResponse:
    code = security.generate_otp()
    db.otp_codes.insert_one(
        {
            "mobile": mobile,
            "code_hash": security.hash_otp(code),
            "purpose": purpose,
            "expires_at": datetime.utcnow() + timedelta(seconds=settings.otp_expire_seconds),
            "consumed": False,
            "attempts": 0,
            "created_at": datetime.utcnow(),
        }
    )

    # TODO: send `code` via a real SMS provider (Twilio / MSG91 / etc.) in production.
    # It's only echoed back here while settings.debug=True, for local testing.
    return schemas.OtpResponse(message="OTP sent", dev_otp=code if settings.debug else None)
