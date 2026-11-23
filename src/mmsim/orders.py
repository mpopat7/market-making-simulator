"""Orders, instructions sent to the engine, and the events it reports back.

Prices are integer ticks and quantities are positive integers. A market
order has no price.
"""

from dataclasses import dataclass
from enum import Enum


class Side(Enum):
    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


@dataclass
class Order:
    """An accepted order and how its quantity has been used so far.

    quantity == filled + canceled + remaining at every point, where
    remaining is what is still resting on the book.
    """

    order_id: str
    owner: str
    side: Side
    price: int | None
    quantity: int
    filled: int = 0
    canceled: int = 0

    @property
    def remaining(self) -> int:
        return self.quantity - self.filled - self.canceled


# Instructions


@dataclass(frozen=True)
class Limit:
    order_id: str
    owner: str
    side: Side
    price: int
    quantity: int


@dataclass(frozen=True)
class Market:
    order_id: str
    owner: str
    side: Side
    quantity: int


@dataclass(frozen=True)
class Cancel:
    order_id: str


Instruction = Limit | Market | Cancel


# Events. seq is the position of the instruction that caused the event.


class RejectReason(Enum):
    DUPLICATE_ID = "duplicate order id"
    BAD_QUANTITY = "quantity must be a positive integer"
    BAD_PRICE = "price must be a positive integer tick"
    UNKNOWN_ORDER = "no order with this id"
    NOT_RESTING = "order is already filled or canceled"


class CancelReason(Enum):
    REQUESTED = "requested"
    NO_LIQUIDITY = "market order remainder had no liquidity"
    SELF_TRADE = "would have traded with the same owner's resting order"


@dataclass(frozen=True)
class Trade:
    seq: int
    buy_order_id: str
    sell_order_id: str
    buyer: str
    seller: str
    price: int
    quantity: int
    aggressor: Side


@dataclass(frozen=True)
class Rested:
    seq: int
    order_id: str
    side: Side
    price: int
    quantity: int


@dataclass(frozen=True)
class Canceled:
    seq: int
    order_id: str
    quantity: int
    reason: CancelReason


@dataclass(frozen=True)
class Rejected:
    seq: int
    order_id: str
    reason: RejectReason


Event = Trade | Rested | Canceled | Rejected
