from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from .. import models, schemas
from ..deps import get_current_user, get_db
from ..game_engine import get_or_create_open_round

router = APIRouter(prefix="/game", tags=["game"])


@router.get("/current-round", response_model=schemas.RoundOut)
def current_round(db: Database = Depends(get_db)):
    round_ = get_or_create_open_round(db)
    remaining = max(0, int((round_["closes_at"] - datetime.utcnow()).total_seconds()))
    return schemas.RoundOut(
        id=str(round_["_id"]),
        status=round_["status"],
        seconds_remaining=remaining,
        drawn_number=round_["drawn_number"],
    )


@router.post("/bets", response_model=schemas.BetOut, status_code=status.HTTP_201_CREATED)
def place_bet(
    payload: schemas.PlaceBetRequest,
    db: Database = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    round_ = get_or_create_open_round(db)
    if round_["status"] != models.RoundStatus.open.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Round is closed, wait for the next one")

    total = payload.stake * len(payload.picks)
    wallet = db.wallets.find_one({"user_id": user["_id"]})
    if float(wallet["balance"]) < total:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Insufficient balance")

    db.wallets.update_one(
        {"user_id": user["_id"]},
        {
            "$inc": {"balance": -total},
            "$set": {"playable": max(0.0, float(wallet["playable"]) - total)},
        },
    )

    bet = {
        "round_id": round_["_id"],
        "user_id": user["_id"],
        "picks": payload.picks,
        "stake": payload.stake,
        "total_amount": total,
        "settled": False,
        "won": False,
        "payout": 0.0,
        "created_at": datetime.utcnow(),
    }
    result = db.bets.insert_one(bet)
    bet["_id"] = result.inserted_id

    db.transactions.insert_one(
        {
            "user_id": user["_id"],
            "type": models.TxnType.bet.value,
            "label": f"Bet placed · {len(payload.picks)} numbers",
            "amount": total,
            "positive": False,
            "created_at": datetime.utcnow(),
        }
    )

    return schemas.BetOut(
        id=str(bet["_id"]),
        round_id=str(bet["round_id"]),
        picks=bet["picks"],
        stake=bet["stake"],
        total_amount=bet["total_amount"],
        settled=bet["settled"],
        won=bet["won"],
        payout=bet["payout"],
    )


@router.get("/last-draws", response_model=schemas.LastDrawsOut)
def last_draws(db: Database = Depends(get_db)):
    rounds = list(
        db.rounds.find({"status": models.RoundStatus.drawn.value}).sort("_id", -1).limit(6)
    )
    return schemas.LastDrawsOut(draws=[r["drawn_number"] for r in rounds])
