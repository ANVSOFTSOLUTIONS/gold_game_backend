import asyncio
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import SessionLocal


def get_or_create_open_round(db: Session) -> models.Round:
    """Returns the single shared round every player currently bets into,
    closing and settling a stale one first if the background loop missed it
    (e.g. right after a server restart)."""
    round_ = (
        db.query(models.Round)
        .filter(models.Round.status == models.RoundStatus.open)
        .order_by(models.Round.id.desc())
        .first()
    )
    if round_ and round_.closes_at > datetime.utcnow():
        return round_
    if round_ and round_.closes_at <= datetime.utcnow():
        close_round(db, round_)

    new_round = models.Round(
        status=models.RoundStatus.open,
        closes_at=datetime.utcnow() + timedelta(seconds=settings.round_length_seconds),
    )
    db.add(new_round)
    db.commit()
    db.refresh(new_round)
    return new_round


def close_round(db: Session, round_: models.Round) -> None:
    """Draws the winning number and settles every unsettled bet in this round."""
    drawn_number = random.randint(1, 9)
    round_.drawn_number = drawn_number
    round_.drawn_at = datetime.utcnow()
    round_.status = models.RoundStatus.drawn
    db.commit()

    bets = (
        db.query(models.Bet)
        .filter(models.Bet.round_id == round_.id, models.Bet.settled.is_(False))
        .all()
    )
    for bet in bets:
        hit = drawn_number in bet.picks
        payout = float(bet.stake) * settings.payout_multiplier if hit else 0.0
        bet.won = hit
        bet.payout = payout
        bet.settled = True

        wallet = (
            db.query(models.Wallet)
            .filter(models.Wallet.user_id == bet.user_id)
            .with_for_update()
            .first()
        )
        if hit:
            wallet.balance = float(wallet.balance) + payout
            wallet.withdrawable = float(wallet.withdrawable) + payout
            wallet.streak += 1
            wallet.points += 110  # +10 base, +100 win bonus (matches frontend)
            db.add(
                models.Transaction(
                    user_id=bet.user_id,
                    type=models.TxnType.win,
                    label=f"Round #{round_.id} · won on {drawn_number}",
                    amount=payout,
                    positive=True,
                )
            )
        else:
            wallet.streak = 0
            wallet.points += 10

    db.commit()


async def round_loop() -> None:
    """Background task started at app startup: ticks every second, closing
    and re-opening rounds on schedule so every player shares the same clock."""
    while True:
        await asyncio.sleep(1)
        db = SessionLocal()
        try:
            round_ = (
                db.query(models.Round)
                .filter(models.Round.status == models.RoundStatus.open)
                .order_by(models.Round.id.desc())
                .first()
            )
            if round_ is None:
                get_or_create_open_round(db)
            elif round_.closes_at <= datetime.utcnow():
                close_round(db, round_)
                get_or_create_open_round(db)
        finally:
            db.close()
