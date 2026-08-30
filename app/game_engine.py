import asyncio
import random
from datetime import datetime, timedelta

from pymongo.database import Database

from . import models
from .config import settings
from .database import db as mongo_db


def get_or_create_open_round(db: Database) -> dict:
    """Returns the single shared round every player currently bets into,
    closing and settling a stale one first if the background loop missed it
    (e.g. right after a server restart)."""
    round_ = db.rounds.find_one({"status": models.RoundStatus.open.value}, sort=[("_id", -1)])
    if round_ and round_["closes_at"] > datetime.utcnow():
        return round_
    if round_ and round_["closes_at"] <= datetime.utcnow():
        close_round(db, round_)

    new_round = {
        "status": models.RoundStatus.open.value,
        "opens_at": datetime.utcnow(),
        "closes_at": datetime.utcnow() + timedelta(seconds=settings.round_length_seconds),
        "drawn_number": None,
        "drawn_at": None,
    }
    result = db.rounds.insert_one(new_round)
    new_round["_id"] = result.inserted_id
    return new_round


def close_round(db: Database, round_: dict) -> None:
    """Draws the winning number and settles every unsettled bet in this round."""
    drawn_number = random.randint(1, 9)
    db.rounds.update_one(
        {"_id": round_["_id"]},
        {
            "$set": {
                "drawn_number": drawn_number,
                "drawn_at": datetime.utcnow(),
                "status": models.RoundStatus.drawn.value,
            }
        },
    )

    bets = list(db.bets.find({"round_id": round_["_id"], "settled": False}))
    for bet in bets:
        hit = drawn_number in bet["picks"]
        payout = float(bet["stake"]) * settings.payout_multiplier if hit else 0.0
        db.bets.update_one(
            {"_id": bet["_id"]},
            {"$set": {"won": hit, "payout": payout, "settled": True}},
        )

        if hit:
            db.wallets.update_one(
                {"user_id": bet["user_id"]},
                {"$inc": {"balance": payout, "withdrawable": payout, "streak": 1, "points": 110}},
            )
            db.transactions.insert_one(
                {
                    "user_id": bet["user_id"],
                    "type": models.TxnType.win.value,
                    "label": f"Round #{round_['_id']} · won on {drawn_number}",
                    "amount": payout,
                    "positive": True,
                    "created_at": datetime.utcnow(),
                }
            )
        else:
            db.wallets.update_one(
                {"user_id": bet["user_id"]},
                {"$set": {"streak": 0}, "$inc": {"points": 10}},
            )


async def round_loop() -> None:
    """Background task started at app startup: ticks every second, closing
    and re-opening rounds on schedule so every player shares the same clock."""
    while True:
        await asyncio.sleep(1)
        round_ = mongo_db.rounds.find_one({"status": models.RoundStatus.open.value}, sort=[("_id", -1)])
        if round_ is None:
            get_or_create_open_round(mongo_db)
        elif round_["closes_at"] <= datetime.utcnow():
            close_round(mongo_db, round_)
            get_or_create_open_round(mongo_db)
