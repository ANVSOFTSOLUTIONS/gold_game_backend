import enum


class RoundStatus(str, enum.Enum):
    open = "open"
    drawn = "drawn"


class TxnType(str, enum.Enum):
    bet = "bet"
    win = "win"
    add_money = "add_money"
    withdraw = "withdraw"
    referral_bonus = "referral_bonus"
