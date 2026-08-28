import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from .database import Base


class RoundStatus(str, enum.Enum):
    open = "open"
    drawn = "drawn"


class TxnType(str, enum.Enum):
    bet = "bet"
    win = "win"
    add_money = "add_money"
    withdraw = "withdraw"
    referral_bonus = "referral_bonus"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    mobile = Column(String(15), unique=True, nullable=False, index=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    wallet = relationship("Wallet", uselist=False, back_populates="user")
    bets = relationship("Bet", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Numeric(12, 2), default=0, nullable=False)
    playable = Column(Numeric(12, 2), default=0, nullable=False)
    withdrawable = Column(Numeric(12, 2), default=0, nullable=False)
    points = Column(Integer, default=0, nullable=False)
    streak = Column(Integer, default=0, nullable=False)

    user = relationship("User", back_populates="wallet")


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True)
    mobile = Column(String(15), index=True, nullable=False)
    code_hash = Column(String, nullable=False)
    purpose = Column(String, nullable=False)  # "signup" | "login"
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, default=False, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Round(Base):
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True)
    status = Column(Enum(RoundStatus), default=RoundStatus.open, nullable=False)
    opens_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closes_at = Column(DateTime, nullable=False)
    drawn_number = Column(Integer, nullable=True)
    drawn_at = Column(DateTime, nullable=True)

    bets = relationship("Bet", back_populates="round")


class Bet(Base):
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    picks = Column(JSON, nullable=False)  # list[int], each 1-9
    stake = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    settled = Column(Boolean, default=False, nullable=False)
    won = Column(Boolean, default=False, nullable=False)
    payout = Column(Numeric(12, 2), default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    round = relationship("Round", back_populates="bets")
    user = relationship("User", back_populates="bets")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(Enum(TxnType), nullable=False)
    label = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    positive = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="transactions")
