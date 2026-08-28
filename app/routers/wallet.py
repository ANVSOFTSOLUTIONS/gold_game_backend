from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_current_user, get_db

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=schemas.WalletOut)
def get_wallet(user: models.User = Depends(get_current_user)):
    return user.wallet


@router.post("/add", response_model=schemas.WalletOut)
def add_money(
    payload: schemas.AddMoneyRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    # NOTE: no real payment gateway is wired up here yet -- this just credits
    # the wallet directly, mirroring the frontend's current mock behaviour.
    # Wire up Razorpay/Stripe/etc. here before handling real money.
    wallet = user.wallet
    wallet.balance = float(wallet.balance) + payload.amount
    wallet.playable = float(wallet.playable) + payload.amount
    db.add(
        models.Transaction(
            user_id=user.id,
            type=models.TxnType.add_money,
            label="Added money",
            amount=payload.amount,
            positive=True,
        )
    )
    db.commit()
    db.refresh(wallet)
    return wallet


@router.post("/withdraw", response_model=schemas.WalletOut)
def withdraw(
    payload: schemas.WithdrawRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    wallet = user.wallet
    amount = min(payload.amount, float(wallet.withdrawable))
    if amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing available to withdraw")

    wallet.balance = max(0.0, float(wallet.balance) - amount)
    wallet.withdrawable = max(0.0, float(wallet.withdrawable) - amount)
    db.add(
        models.Transaction(
            user_id=user.id,
            type=models.TxnType.withdraw,
            label="Withdrawal",
            amount=amount,
            positive=False,
        )
    )
    db.commit()
    db.refresh(wallet)
    return wallet


@router.get("/transactions", response_model=list[schemas.TransactionOut])
def list_transactions(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == user.id)
        .order_by(models.Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
