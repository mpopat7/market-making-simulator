"""Matching rules and rejections beyond the worked sequence."""

import random

from mmsim import (
    Cancel,
    Canceled,
    CancelReason,
    Limit,
    Market,
    MatchingEngine,
    Rejected,
    RejectReason,
    Rested,
    Side,
    Trade,
    check_invariants,
)


def engine_with(*instructions) -> MatchingEngine:
    engine = MatchingEngine()
    for instruction in instructions:
        engine.submit(instruction)
    return engine


def test_crossing_limit_trades_at_resting_price_and_rests_remainder():
    engine = engine_with(Limit("S1", "a", Side.SELL, 100, 3))
    events = engine.submit(Limit("B1", "b", Side.BUY, 102, 5))
    assert events == [
        Trade(2, "B1", "S1", "b", "a", 100, 3, Side.BUY),
        Rested(2, "B1", Side.BUY, 102, 2),
    ]
    assert engine.book.snapshot() == {"bids": [(102, [("B1", 2)])], "asks": []}
    check_invariants(engine)


def test_non_crossing_limit_rests_without_trading():
    engine = engine_with(Limit("S1", "a", Side.SELL, 100, 3))
    events = engine.submit(Limit("B1", "b", Side.BUY, 99, 5))
    assert events == [Rested(2, "B1", Side.BUY, 99, 5)]
    check_invariants(engine)


def test_sweeps_multiple_levels_best_price_first():
    engine = engine_with(
        Limit("S3", "a", Side.SELL, 103, 2),
        Limit("S1", "a", Side.SELL, 101, 2),
        Limit("S2", "a", Side.SELL, 102, 2),
    )
    events = engine.submit(Limit("B1", "b", Side.BUY, 102, 5))
    assert [(e.sell_order_id, e.price, e.quantity) for e in events if isinstance(e, Trade)] == [
        ("S1", 101, 2),
        ("S2", 102, 2),
    ]
    # The limit stops the sweep before 103; the remaining 1 rests at 102.
    assert engine.book.snapshot() == {"bids": [(102, [("B1", 1)])], "asks": [(103, [("S3", 2)])]}
    check_invariants(engine)


def test_partially_filled_order_keeps_its_place():
    engine = engine_with(
        Limit("B1", "a", Side.BUY, 99, 5),
        Limit("B2", "b", Side.BUY, 99, 5),
    )
    engine.submit(Market("S1", "c", Side.SELL, 2))
    events = engine.submit(Market("S2", "c", Side.SELL, 4))
    assert [(e.buy_order_id, e.quantity) for e in events] == [("B1", 3), ("B2", 1)]
    check_invariants(engine)


def test_cancel_does_not_reorder_the_queue():
    engine = engine_with(
        Limit("B1", "a", Side.BUY, 99, 1),
        Limit("B2", "a", Side.BUY, 99, 1),
        Limit("B3", "a", Side.BUY, 99, 1),
        Cancel("B2"),
    )
    assert engine.book.snapshot()["bids"] == [(99, [("B1", 1), ("B3", 1)])]
    check_invariants(engine)


def test_market_order_into_empty_book_is_canceled_not_rested():
    engine = MatchingEngine()
    events = engine.submit(Market("B1", "a", Side.BUY, 4))
    assert events == [Canceled(1, "B1", 4, CancelReason.NO_LIQUIDITY)]
    assert engine.book.snapshot() == {"bids": [], "asks": []}
    check_invariants(engine)


def test_rejections():
    engine = engine_with(Limit("S1", "a", Side.SELL, 100, 1))
    cases = [
        (Limit("S1", "b", Side.SELL, 101, 1), RejectReason.DUPLICATE_ID),
        (Market("S1", "b", Side.BUY, 1), RejectReason.DUPLICATE_ID),
        (Limit("X1", "b", Side.BUY, 99, 0), RejectReason.BAD_QUANTITY),
        (Limit("X2", "b", Side.BUY, 99, -3), RejectReason.BAD_QUANTITY),
        (Market("X3", "b", Side.BUY, 0), RejectReason.BAD_QUANTITY),
        (Limit("X4", "b", Side.BUY, 99, True), RejectReason.BAD_QUANTITY),
        (Limit("X5", "b", Side.BUY, 0, 1), RejectReason.BAD_PRICE),
        (Limit("X6", "b", Side.BUY, 99.5, 1), RejectReason.BAD_PRICE),
        (Cancel("nope"), RejectReason.UNKNOWN_ORDER),
    ]
    for instruction, reason in cases:
        events = engine.submit(instruction)
        assert events == [Rejected(engine.seq, instruction.order_id, reason)], instruction

    # Rejections leave the book and the order records untouched.
    assert engine.book.snapshot() == {"bids": [], "asks": [(100, [("S1", 1)])]}
    assert set(engine.orders) == {"S1"}
    check_invariants(engine)


def test_cancel_of_completed_orders_is_rejected():
    engine = engine_with(
        Limit("S1", "a", Side.SELL, 100, 1),
        Market("B1", "b", Side.BUY, 1),  # fills S1 completely
        Limit("S2", "a", Side.SELL, 100, 1),
        Cancel("S2"),
    )
    for order_id in ("S1", "B1", "S2"):
        assert engine.submit(Cancel(order_id)) == [
            Rejected(engine.seq, order_id, RejectReason.NOT_RESTING)
        ]
    check_invariants(engine)


def test_self_trade_cancels_incoming_after_trading_ahead_of_own_order():
    engine = engine_with(
        Limit("S1", "other", Side.SELL, 100, 2),
        Limit("S2", "mm", Side.SELL, 100, 3),
        Limit("S3", "other", Side.SELL, 100, 4),
    )
    events = engine.submit(Limit("B1", "mm", Side.BUY, 101, 6))
    assert events == [
        Trade(4, "B1", "S1", "mm", "other", 100, 2, Side.BUY),
        Canceled(4, "B1", 4, CancelReason.SELF_TRADE),
    ]
    # The owner's resting order is untouched and the incoming order does not rest.
    assert engine.book.snapshot() == {"bids": [], "asks": [(100, [("S2", 3), ("S3", 4)])]}
    check_invariants(engine)


def test_self_trade_on_market_order():
    engine = engine_with(Limit("B1", "mm", Side.BUY, 99, 5))
    assert engine.submit(Market("S1", "mm", Side.SELL, 2)) == [
        Canceled(2, "S1", 2, CancelReason.SELF_TRADE)
    ]
    check_invariants(engine)


def test_random_flow_keeps_invariants():
    rng = random.Random(7)
    engine = MatchingEngine()
    live: list[str] = []
    for n in range(2000):
        roll = rng.random()
        side = rng.choice(list(Side))
        if roll < 0.15 and live:
            engine.submit(Cancel(live.pop(rng.randrange(len(live)))))
        elif roll < 0.3:
            engine.submit(Market(f"M{n}", f"p{rng.randrange(4)}", side, rng.randint(1, 8)))
        else:
            price = rng.randint(95, 105)
            events = engine.submit(Limit(f"L{n}", f"p{rng.randrange(4)}", side, price, rng.randint(1, 8)))
            if any(isinstance(e, Rested) for e in events):
                live.append(f"L{n}")
        check_invariants(engine)
