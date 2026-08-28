from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..config import settings
from ..deps import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.OtpResponse)
def signup(payload: schemas.SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.mobile == payload.mobile).first()
    if existing and existing.is_verified:
        raise HTTPException(status.HTTP_409_CONFLICT, "Mobile number already registered")

    if not existing:
        existing = models.User(full_name=payload.full_name, mobile=payload.mobile, is_verified=False)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        db.add(models.Wallet(user_id=existing.id))
        db.commit()

    return _issue_otp(db, payload.mobile, purpose="signup")


@router.post("/request-otp", response_model=schemas.OtpResponse)
def request_otp(payload: schemas.RequestOtpRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.mobile == payload.mobile).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account with this mobile number")
    return _issue_otp(db, payload.mobile, purpose="login")


@router.post("/verify-otp", response_model=schemas.TokenResponse)
def verify_otp(payload: schemas.VerifyOtpRequest, db: Session = Depends(get_db)):
    otp = (
        db.query(models.OtpCode)
        .filter(models.OtpCode.mobile == payload.mobile, models.OtpCode.consumed.is_(False))
        .order_by(models.OtpCode.id.desc())
        .first()
    )
    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OTP expired or not found, please request a new one")
    if otp.attempts >= 5:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, request a new OTP")

    otp.attempts += 1
    db.commit()

    if not security.verify_otp_hash(payload.code, otp.code_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect OTP")

    otp.consumed = True

    user = db.query(models.User).filter(models.User.mobile == payload.mobile).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user.is_verified = True
    db.commit()

    token = security.create_access_token(user.id, user.mobile)
    return schemas.TokenResponse(access_token=token)


def _issue_otp(db: Session, mobile: str, purpose: str) -> schemas.OtpResponse:
    code = security.generate_otp()
    otp = models.OtpCode(
        mobile=mobile,
        code_hash=security.hash_otp(code),
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(seconds=settings.otp_expire_seconds),
    )
    db.add(otp)
    db.commit()

    # TODO: send `code` via a real SMS provider (Twilio / MSG91 / etc.) in production.
    # It's only echoed back here while settings.debug=True, for local testing.
    return schemas.OtpResponse(message="OTP sent", dev_otp=code if settings.debug else None)
