"""Deliberately broken books, to show the worked-sequence test catches them.

If one of these ever passes the worked sequence, the tests are too weak.
"""

from mmsim import Limit, Market, MatchingEngine, OrderBook, Side

from test_worked_sequence import SEQUENCE


class LastInFirstOut(OrderBook):
    """Matches the newest order at the best price instead of the oldest."""

    def best_order(self, side):
        price = self.best_price(side)
        return None if price is None else self._levels[side][price][-1]


class PartialFillLosesPriority(OrderBook):
    """Sends an order to the back of its queue after it is partly filled."""

    def best_order(self, side):
        price = self.best_price(side)
        if price is None:
            return None
        level = self._levels[side][price]
        while level[0].filled > 0 and len(level) > 1 and any(o.filled == 0 for o in level):
            level.rotate(-1)
        return level[0]


def first_divergence(book: OrderBook) -> int | None:
    engine = MatchingEngine(book)
    for step, (instruction, expected_events, expected_book) in enumerate(SEQUENCE, start=1):
        if engine.submit(instruction) != expected_events or engine.book.snapshot() != expected_book:
            return step
    return None


def test_lifo_book_fails_at_the_first_trade():
    # Event 3 should take S1 first; a LIFO book takes S2 first.
    assert first_divergence(LastInFirstOut()) == 3


def test_partial_fill_priority_bug_is_caught():
    # The worked sequence fully fills S1 before touching S2, so it cannot see
    # this bug. A second partial fill at one level is needed to expose it.
    def run(book):
        engine = MatchingEngine(book)
        engine.submit(Limit("B1", "a", Side.BUY, 99, 5))
        engine.submit(Limit("B2", "b", Side.BUY, 99, 5))
        engine.submit(Market("S1", "c", Side.SELL, 2))
        return [(t.buy_order_id, t.quantity) for t in engine.submit(Market("S2", "c", Side.SELL, 4))]

    assert run(OrderBook()) == [("B1", 3), ("B2", 1)]
    assert run(PartialFillLosesPriority()) != [("B1", 3), ("B2", 1)]
