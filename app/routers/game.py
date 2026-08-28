from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_current_user, get_db
from ..game_engine import get_or_create_open_round

router = APIRouter(prefix="/game", tags=["game"])


@router.get("/current-round", response_model=schemas.RoundOut)
def current_round(db: Session = Depends(get_db)):
    round_ = get_or_create_open_round(db)
    remaining = max(0, int((round_.closes_at - datetime.utcnow()).total_seconds()))
    return schemas.RoundOut(
        id=round_.id,
        status=round_.status.value,
        seconds_remaining=remaining,
        drawn_number=round_.drawn_number,
    )


@router.post("/bets", response_model=schemas.BetOut, status_code=status.HTTP_201_CREATED)
def place_bet(
    payload: schemas.PlaceBetRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    round_ = get_or_create_open_round(db)
    if round_.status != models.RoundStatus.open:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Round is closed, wait for the next one")

    total = payload.stake * len(payload.picks)
    wallet = user.wallet
    if float(wallet.balance) < total:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Insufficient balance")

    wallet.balance = float(wallet.balance) - total
    wallet.playable = max(0.0, float(wallet.playable) - total)

    bet = models.Bet(
        round_id=round_.id,
        user_id=user.id,
        picks=payload.picks,
        stake=payload.stake,
        total_amount=total,
    )
    db.add(bet)
    db.add(
        models.Transaction(
            user_id=user.id,
            type=models.TxnType.bet,
            label=f"Bet placed · {len(payload.picks)} numbers",
            amount=total,
            positive=False,
        )
    )
    db.commit()
    db.refresh(bet)
    return bet


@router.get("/last-draws", response_model=schemas.LastDrawsOut)
def last_draws(db: Session = Depends(get_db)):
    rounds = (
        db.query(models.Round)
        .filter(models.Round.status == models.RoundStatus.drawn)
        .order_by(models.Round.id.desc())
        .limit(6)
        .all()
    )
    return schemas.LastDrawsOut(draws=[r.drawn_number for r in rounds])
