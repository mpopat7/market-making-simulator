"""Fill-model rules on hand-built books, plus whole-run determinism."""

from mmsim import Cancel, Limit, Market, Side
from mmsim.agents import Ledger
from mmsim.experiment import run_seed
from mmsim.venues import EngineVenue, VirtualVenue
from mmsim.world import Params, World


def setup(model):
    world = World(Params(), seed=0)  # used only as an engine holder here
    ledger = Ledger()
    venue = VirtualVenue(world, ledger, model)
    return world, ledger, venue


def rest_three_ahead(world):
    world.send(Limit("A1", "bg", Side.SELL, 101, 3))


def test_touch_fills_on_any_trade_at_price():
    world, ledger, venue = setup("touch")
    rest_three_ahead(world)
    venue.submit(Limit("mm1", "mm", Side.SELL, 101, 2))
    world.send(Market("T1", "bt", Side.BUY, 1))
    assert ledger.filled["mm1"] == 2


def test_through_needs_a_print_beyond_the_price():
    world, ledger, venue = setup("through")
    rest_three_ahead(world)
    world.send(Limit("A2", "bg", Side.SELL, 102, 5))
    venue.submit(Limit("mm1", "mm", Side.SELL, 101, 2))
    world.send(Market("T1", "bt", Side.BUY, 3))  # prints only at 101
    assert ledger.filled["mm1"] == 0
    world.send(Market("T2", "bt", Side.BUY, 1))  # prints at 102
    assert ledger.filled["mm1"] == 2


def test_queue_model_waits_for_quantity_ahead():
    world, ledger, venue = setup("queue")
    rest_three_ahead(world)
    world.send(Limit("A2", "bg", Side.SELL, 101, 3))
    venue.submit(Limit("mm1", "mm", Side.SELL, 101, 2))
    assert venue.orders["mm1"].ahead == 6
    world.send(Market("T1", "bt", Side.BUY, 5))
    assert ledger.filled["mm1"] == 0 and venue.orders["mm1"].ahead == 1
    world.send(Market("T2", "bt", Side.BUY, 1))  # last unit ahead; nothing left for us
    assert ledger.filled["mm1"] == 0


def test_queue_model_shrinks_ahead_on_cancels():
    world, ledger, venue = setup("queue")
    world.send(Limit("A1", "bg", Side.SELL, 101, 4))
    world.send(Limit("A2", "bg", Side.SELL, 101, 4))
    venue.submit(Limit("mm1", "mm", Side.SELL, 101, 2))

    world.send(Cancel("A2"))  # 4 of 8 at the level canceled: ahead halves
    assert venue.orders["mm1"].ahead == 4


def test_oracle_fills_when_orders_behind_us_trade():
    world, ledger, venue = setup("oracle")
    rest_three_ahead(world)
    venue.submit(Limit("mm1", "mm", Side.SELL, 101, 2))
    world.send(Limit("A2", "bg", Side.SELL, 101, 4))  # arrives after us
    world.send(Market("T1", "bt", Side.BUY, 3))  # takes A1, which was ahead
    assert ledger.filled["mm1"] == 0
    world.send(Market("T2", "bt", Side.BUY, 3))  # takes A2, which was behind us
    assert ledger.filled["mm1"] == 2


def test_virtual_quote_crossing_the_book_takes_displayed_liquidity():
    world, ledger, venue = setup("queue")
    rest_three_ahead(world)
    venue.submit(Limit("mm1", "mm", Side.BUY, 101, 5))
    assert ledger.filled["mm1"] == 3 and ledger.maker_volume == 0
    assert venue.orders["mm1"].remaining == 2
    # The background book is untouched by a virtual order.
    assert world.engine.book.snapshot()["asks"] == [(101, [("A1", 3)])]


def test_virtual_venue_cannot_take_the_same_displayed_order_twice():
    world, ledger, venue = setup("queue")
    rest_three_ahead(world)
    venue.submit(Limit("mm1", "mm", Side.BUY, 101, 2))
    venue.submit(Limit("mm2", "mm", Side.BUY, 101, 2))
    assert ledger.filled["mm1"] == 2 and ledger.filled["mm2"] == 1
    assert venue.orders["mm2"].remaining == 1


def test_engine_venue_ledger_matches_engine_accounting():
    world = World(Params(), seed=0)
    ledger = Ledger()
    venue = EngineVenue(world, ledger)
    venue.submit(Limit("mm1", "mm", Side.BUY, 99, 3))
    world.send(Market("T1", "bt", Side.SELL, 2))
    assert ledger.position == world.engine.inventory["mm"] == 2
    assert ledger.cash == world.engine.cash["mm"] == -198


def test_run_seed_is_deterministic():
    assert run_seed(0.02, 0.3, 3, delays=(1,)) == run_seed(0.02, 0.3, 3, delays=(1,))
