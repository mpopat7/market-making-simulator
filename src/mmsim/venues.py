"""Where the market maker's orders go: the real engine, or a fill model.

EngineVenue is the reference: orders enter the world's matching engine.
VirtualVenue keeps the orders out of the book and estimates fills from the
background-only world's events, using one of the models in
docs/EXPERIMENT.md, section 3.
"""

from dataclasses import dataclass, field

from .agents import Ledger
from .orders import Cancel, Canceled, Limit, Side, Trade

MODELS = ("touch", "through", "queue", "oracle")


class EngineVenue:
    def __init__(self, world, ledger: Ledger) -> None:
        self.world = world
        self.ledger = ledger
        world.observers.append(self)

    def submit(self, instruction) -> None:
        if isinstance(instruction, Limit):
            self.ledger.register(instruction.order_id, instruction.quantity)
        self.world.send(instruction)

    def on_events(self, events, world) -> None:
        for event in events:
            if isinstance(event, Trade):
                for order_id, side in ((event.buy_order_id, Side.BUY), (event.sell_order_id, Side.SELL)):
                    if order_id in self.ledger.size:
                        maker = event.aggressor is not side
                        self.ledger.fill(order_id, side, event.price, event.quantity, maker)
            elif isinstance(event, Canceled) and event.order_id in self.ledger.size:
                self.ledger.close(event.order_id)


@dataclass
class VirtualOrder:
    order_id: str
    side: Side
    price: int
    remaining: int
    ahead: float = 0.0  # queue model: estimated quantity ahead
    ahead_ids: set[str] = field(default_factory=set)  # oracle: exact orders ahead


def _better_or_equal(side: Side, price: int, limit: int) -> bool:
    """Whether a resting order at `price` is at least as good as `limit` for the
    aggressor trading against `side`."""
    return price <= limit if side is Side.SELL else price >= limit


class VirtualVenue:
    def __init__(self, world, ledger: Ledger, model: str) -> None:
        assert model in MODELS, model
        self.world = world
        self.ledger = ledger
        self.model = model
        self.orders: dict[str, VirtualOrder] = {}
        # Displayed liquidity this venue has already taken. The background
        # book never loses it, so without this record the same stale order
        # could be taken again on every requote.
        self.taken: dict[str, int] = {}
        world.observers.append(self)

    def submit(self, instruction) -> None:
        if isinstance(instruction, Cancel):
            if self.orders.pop(instruction.order_id, None) is not None:
                self.ledger.close(instruction.order_id)
            return

        ins: Limit = instruction
        self.ledger.register(ins.order_id, ins.quantity)
        remaining = self._take_displayed(ins)
        if remaining == 0:
            return
        book = self.world.engine.book
        level = book.level(ins.side, ins.price)
        self.orders[ins.order_id] = VirtualOrder(
            ins.order_id,
            ins.side,
            ins.price,
            remaining,
            ahead=float(sum(o.remaining for o in level)),
            ahead_ids={o.order_id for o in level},
        )

    def _take_displayed(self, ins: Limit) -> int:
        """A quote that crosses the displayed book trades immediately against
        it, at the displayed prices. The book itself is not changed, but each
        displayed unit can be taken only once."""
        remaining = ins.quantity
        for resting in self.world.engine.book.orders(ins.side.opposite):
            if remaining == 0 or not _better_or_equal(resting.side, resting.price, ins.price):
                break
            quantity = min(remaining, resting.remaining - self.taken.get(resting.order_id, 0))
            if quantity <= 0:
                continue
            self.taken[resting.order_id] = self.taken.get(resting.order_id, 0) + quantity
            self.ledger.fill(ins.order_id, ins.side, resting.price, quantity, maker=False)
            remaining -= quantity
        return remaining

    def on_events(self, events, world) -> None:
        for event in events:
            if isinstance(event, Trade):
                self._on_trade(event)
            elif isinstance(event, Canceled):
                self._on_cancel(event)

    def _fill(self, order: VirtualOrder, quantity: int) -> None:
        if quantity <= 0:
            return
        self.ledger.fill(order.order_id, order.side, order.price, quantity, maker=True)
        order.remaining -= quantity
        if order.remaining == 0:
            del self.orders[order.order_id]

    def _on_trade(self, trade: Trade) -> None:
        resting_side = Side.SELL if trade.aggressor is Side.BUY else Side.BUY
        resting_id = trade.sell_order_id if resting_side is Side.SELL else trade.buy_order_id
        candidates = [o for o in self.orders.values() if o.side is resting_side]
        # Best-priced virtual order first, then placement order.
        candidates.sort(key=lambda o: o.price if resting_side is Side.SELL else -o.price)
        available = trade.quantity

        for order in candidates:
            through = (
                trade.price > order.price if resting_side is Side.SELL else trade.price < order.price
            )
            at = trade.price == order.price
            if not (through or at):
                continue
            model = self.model

            if model == "touch":
                self._fill(order, order.remaining)
            elif model == "through":
                if through:
                    self._fill(order, order.remaining)
            elif model == "queue":
                if through:
                    self._fill(order, order.remaining)
                else:
                    consumed = min(order.ahead, available)
                    order.ahead -= consumed
                    quantity = min(order.remaining, int(available - consumed))
                    available -= consumed + quantity
                    self._fill(order, quantity)
            else:  # oracle
                if at and resting_id in order.ahead_ids:
                    continue  # the trade hit an order genuinely ahead of ours
                quantity = min(order.remaining, available)
                available -= quantity
                self._fill(order, quantity)

    def _on_cancel(self, event: Canceled) -> None:
        canceled = self.world.engine.orders[event.order_id]
        if canceled.price is None:
            return  # a market order remainder, never on the book
        level_after = sum(o.remaining for o in self.world.engine.book.level(canceled.side, canceled.price))
        level_before = level_after + event.quantity
        for order in self.orders.values():
            if order.side is not canceled.side or order.price != canceled.price:
                continue
            if self.model == "queue" and level_before > 0:
                order.ahead -= event.quantity * order.ahead / level_before
            elif self.model == "oracle":
                order.ahead_ids.discard(event.order_id)
