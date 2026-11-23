"""The six-event sequence from docs/PLAN.md, checked after every event."""

from mmsim import (
    Cancel,
    Canceled,
    CancelReason,
    Limit,
    Market,
    MatchingEngine,
    Rested,
    Side,
    Trade,
    check_invariants,
)

EMPTY = {"bids": [], "asks": []}

# (instruction, expected events, expected book afterward)
SEQUENCE = [
    (
        Limit("S1", "alice", Side.SELL, 100, 5),
        [Rested(1, "S1", Side.SELL, 100, 5)],
        {"bids": [], "asks": [(100, [("S1", 5)])]},
    ),
    (
        Limit("S2", "bob", Side.SELL, 100, 4),
        [Rested(2, "S2", Side.SELL, 100, 4)],
        {"bids": [], "asks": [(100, [("S1", 5), ("S2", 4)])]},
    ),
    (
        Market("B1", "carol", Side.BUY, 6),
        [
            Trade(3, "B1", "S1", "carol", "alice", 100, 5, Side.BUY),
            Trade(3, "B1", "S2", "carol", "bob", 100, 1, Side.BUY),
        ],
        {"bids": [], "asks": [(100, [("S2", 3)])]},
    ),
    (
        Cancel("S2"),
        [Canceled(4, "S2", 3, CancelReason.REQUESTED)],
        EMPTY,
    ),
    (
        Limit("B2", "dave", Side.BUY, 99, 2),
        [Rested(5, "B2", Side.BUY, 99, 2)],
        {"bids": [(99, [("B2", 2)])], "asks": []},
    ),
    (
        Market("S3", "erin", Side.SELL, 3),
        [
            Trade(6, "B2", "S3", "dave", "erin", 99, 2, Side.SELL),
            Canceled(6, "S3", 1, CancelReason.NO_LIQUIDITY),
        ],
        EMPTY,
    ),
]


def replay(engine: MatchingEngine) -> list:
    log = []
    for instruction, _, _ in SEQUENCE:
        log.append((engine.submit(instruction), engine.book.snapshot()))
    return log


def test_each_event_matches_the_plan():
    engine = MatchingEngine()
    for step, (instruction, expected_events, expected_book) in enumerate(SEQUENCE, start=1):
        assert engine.submit(instruction) == expected_events, f"events after event {step}"
        assert engine.book.snapshot() == expected_book, f"book after event {step}"
        check_invariants(engine)


def test_final_order_accounting():
    engine = MatchingEngine()
    replay(engine)
    # (filled, canceled, remaining) for each order
    expected = {
        "S1": (5, 0, 0),
        "S2": (1, 3, 0),
        "B1": (6, 0, 0),
        "B2": (2, 0, 0),
        "S3": (2, 1, 0),
    }
    actual = {oid: (o.filled, o.canceled, o.remaining) for oid, o in engine.orders.items()}
    assert actual == expected


def test_final_cash_and_inventory():
    engine = MatchingEngine()
    replay(engine)
    assert dict(engine.inventory) == {"carol": 6, "alice": -5, "bob": -1, "dave": 2, "erin": -2}
    assert dict(engine.cash) == {"carol": -600, "alice": 500, "bob": 100, "dave": -198, "erin": 198}


def test_replay_is_deterministic():
    assert replay(MatchingEngine()) == replay(MatchingEngine())
