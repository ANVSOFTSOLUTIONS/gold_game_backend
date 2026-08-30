from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from .. import models, schemas
from ..deps import get_current_user, get_db

router = APIRouter(prefix="/wallet", tags=["wallet"])


def _wallet_out(wallet: dict) -> schemas.WalletOut:
    return schemas.WalletOut(
        balance=float(wallet["balance"]),
        playable=float(wallet["playable"]),
        withdrawable=float(wallet["withdrawable"]),
        points=wallet["points"],
        streak=wallet["streak"],
    )


@router.get("", response_model=schemas.WalletOut)
def get_wallet(db: Database = Depends(get_db), user: dict = Depends(get_current_user)):
    wallet = db.wallets.find_one({"user_id": user["_id"]})
    return _wallet_out(wallet)


@router.post("/add", response_model=schemas.WalletOut)
def add_money(
    payload: schemas.AddMoneyRequest,
    db: Database = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # NOTE: no real payment gateway is wired up here yet -- this just credits
    # the wallet directly, mirroring the frontend's current mock behaviour.
    # Wire up Razorpay/Stripe/etc. here before handling real money.
    db.wallets.update_one(
        {"user_id": user["_id"]},
        {"$inc": {"balance": payload.amount, "playable": payload.amount}},
    )
    db.transactions.insert_one(
        {
            "user_id": user["_id"],
            "type": models.TxnType.add_money.value,
            "label": "Added money",
            "amount": payload.amount,
            "positive": True,
            "created_at": datetime.utcnow(),
        }
    )
    wallet = db.wallets.find_one({"user_id": user["_id"]})
    return _wallet_out(wallet)


@router.post("/withdraw", response_model=schemas.WalletOut)
def withdraw(
    payload: schemas.WithdrawRequest,
    db: Database = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    wallet = db.wallets.find_one({"user_id": user["_id"]})
    amount = min(payload.amount, float(wallet["withdrawable"]))
    if amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing available to withdraw")

    db.wallets.update_one(
        {"user_id": user["_id"]},
        {
            "$set": {
                "balance": max(0.0, float(wallet["balance"]) - amount),
                "withdrawable": max(0.0, float(wallet["withdrawable"]) - amount),
            }
        },
    )
    db.transactions.insert_one(
        {
            "user_id": user["_id"],
            "type": models.TxnType.withdraw.value,
            "label": "Withdrawal",
            "amount": amount,
            "positive": False,
            "created_at": datetime.utcnow(),
        }
    )
    wallet = db.wallets.find_one({"user_id": user["_id"]})
    return _wallet_out(wallet)


@router.get("/transactions", response_model=list[schemas.TransactionOut])
def list_transactions(
    limit: int = 20,
    offset: int = 0,
    db: Database = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    cursor = (
        db.transactions.find({"user_id": user["_id"]})
        .sort("created_at", -1)
        .skip(offset)
        .limit(limit)
    )
    return [
        schemas.TransactionOut(
            id=str(t["_id"]),
            type=t["type"],
            label=t["label"],
            amount=float(t["amount"]),
            positive=t["positive"],
            created_at=t["created_at"],
        )
        for t in cursor
    ]
