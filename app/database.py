from pymongo import MongoClient
from pymongo.database import Database

from .config import settings

client = MongoClient(settings.database_url)
db: Database = client.get_default_database()


def init_indexes() -> None:
    db.users.create_index("mobile", unique=True)
    db.wallets.create_index("user_id", unique=True)
    db.otp_codes.create_index("mobile")
    db.rounds.create_index("status")
    db.bets.create_index("round_id")
    db.bets.create_index("user_id")
    db.transactions.create_index("user_id")
