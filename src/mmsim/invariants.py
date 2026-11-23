"""Checks that must hold after every instruction, whatever the order flow."""

from .engine import MatchingEngine
from .orders import Side


def check_invariants(engine: MatchingEngine) -> None:
    """Raise AssertionError if the engine's state is inconsistent."""
    resting = {}
    for side in Side:
        for order in engine.book.orders(side):
            assert order.side is side, f"{order.order_id} is on the wrong side"
            assert order.remaining > 0, f"{order.order_id} rests with no quantity"
            assert order.order_id not in resting, f"{order.order_id} rests twice"
            resting[order.order_id] = order

    for order in engine.orders.values():
        assert order.filled >= 0 and order.canceled >= 0
        assert order.filled + order.canceled + order.remaining == order.quantity
        on_book = order.order_id in resting
        assert on_book == (order.remaining > 0), f"{order.order_id} book state mismatch"
        if order.price is None:
            assert not on_book, f"market order {order.order_id} is resting"

    bid, ask = engine.book.best_price(Side.BUY), engine.book.best_price(Side.SELL)
    assert bid is None or ask is None or bid < ask, f"crossed book: bid {bid} >= ask {ask}"

    assert sum(engine.inventory.values()) == 0, "inventory does not net to zero"
    assert sum(engine.cash.values()) == 0, "cash does not net to zero"
