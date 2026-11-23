"""Single-instrument matching engine with price/time priority.

Instructions are processed one at a time in submission order. Each call to
submit() returns the events that instruction caused, in the order they
happened.

Self-trade prevention: when an incoming order reaches a resting order from
the same owner, the incoming remainder is canceled ("cancel newest"). Trades
already made against other owners stand, and the resting order keeps its
place. The engine also keeps each owner's cash and inventory; cash is in
tick units (price * quantity) and there are no fees yet.
"""

from collections import defaultdict

from .book import OrderBook
from .orders import (
    Cancel,
    Canceled,
    CancelReason,
    Event,
    Instruction,
    Limit,
    Market,
    Order,
    Rejected,
    RejectReason,
    Rested,
    Side,
    Trade,
)


def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0


class MatchingEngine:
    def __init__(self, book: OrderBook | None = None) -> None:
        self.book = book if book is not None else OrderBook()
        self.orders: dict[str, Order] = {}
        self.inventory: defaultdict[str, int] = defaultdict(int)
        self.cash: defaultdict[str, int] = defaultdict(int)
        self.seq = 0

    def submit(self, instruction: Instruction) -> list[Event]:
        self.seq += 1
        match instruction:
            case Limit():
                return self._limit(instruction)
            case Market():
                return self._market(instruction)
            case Cancel():
                return self._cancel(instruction)
        raise TypeError(f"unknown instruction: {instruction!r}")

    def _reject(self, order_id: str, reason: RejectReason) -> list[Event]:
        return [Rejected(self.seq, order_id, reason)]

    def _check_new(self, order_id: str, quantity: int) -> RejectReason | None:
        if order_id in self.orders:
            return RejectReason.DUPLICATE_ID
        if not _positive_int(quantity):
            return RejectReason.BAD_QUANTITY
        return None

    def _limit(self, ins: Limit) -> list[Event]:
        if reason := self._check_new(ins.order_id, ins.quantity):
            return self._reject(ins.order_id, reason)
        if not _positive_int(ins.price):
            return self._reject(ins.order_id, RejectReason.BAD_PRICE)

        order = Order(ins.order_id, ins.owner, ins.side, ins.price, ins.quantity)
        self.orders[order.order_id] = order
        events = self._match(order)
        if order.remaining > 0:
            self.book.add(order)
            events.append(Rested(self.seq, order.order_id, order.side, order.price, order.remaining))
        return events

    def _market(self, ins: Market) -> list[Event]:
        if reason := self._check_new(ins.order_id, ins.quantity):
            return self._reject(ins.order_id, reason)

        order = Order(ins.order_id, ins.owner, ins.side, None, ins.quantity)
        self.orders[order.order_id] = order
        events = self._match(order)
        if order.remaining > 0:
            # A market order never rests; whatever is left is canceled.
            leftover = order.remaining
            order.canceled += leftover
            events.append(Canceled(self.seq, order.order_id, leftover, CancelReason.NO_LIQUIDITY))
        return events

    def _cancel(self, ins: Cancel) -> list[Event]:
        order = self.orders.get(ins.order_id)
        if order is None:
            return self._reject(ins.order_id, RejectReason.UNKNOWN_ORDER)
        if order.remaining == 0:
            return self._reject(ins.order_id, RejectReason.NOT_RESTING)

        leftover = order.remaining
        self.book.remove(order)
        order.canceled += leftover
        return [Canceled(self.seq, order.order_id, leftover, CancelReason.REQUESTED)]

    def _crosses(self, incoming: Order, resting_price: int) -> bool:
        if incoming.price is None:
            return True
        if incoming.side is Side.BUY:
            return incoming.price >= resting_price
        return incoming.price <= resting_price

    def _match(self, incoming: Order) -> list[Event]:
        """Trade the incoming order against the opposite side until it is
        filled, the best opposite price no longer crosses, the side is empty,
        or the next resting order belongs to the same owner.
        """
        events: list[Event] = []
        while incoming.remaining > 0:
            resting = self.book.best_order(incoming.side.opposite)
            if resting is None or not self._crosses(incoming, resting.price):
                break
            if resting.owner == incoming.owner:
                leftover = incoming.remaining
                incoming.canceled += leftover
                events.append(
                    Canceled(self.seq, incoming.order_id, leftover, CancelReason.SELF_TRADE)
                )
                break

            quantity = min(incoming.remaining, resting.remaining)
            price = resting.price  # trades happen at the resting order's price
            incoming.filled += quantity
            resting.filled += quantity
            if resting.remaining == 0:
                self.book.remove(resting)
            # A partially filled resting order is left where it is, so it keeps
            # its place at the front of the queue.

            buy, sell = (incoming, resting) if incoming.side is Side.BUY else (resting, incoming)
            self.inventory[buy.owner] += quantity
            self.inventory[sell.owner] -= quantity
            self.cash[buy.owner] -= price * quantity
            self.cash[sell.owner] += price * quantity
            events.append(
                Trade(
                    self.seq,
                    buy.order_id,
                    sell.order_id,
                    buy.owner,
                    sell.owner,
                    price,
                    quantity,
                    incoming.side,
                )
            )
        return events
