"""Market maker strategies, the quoting agent, and its ledger.

An Agent sends limit orders and cancels to a venue (reference or approximate)
and learns about its fills through a Ledger the venue updates. A replay agent
is an Agent with no strategy and a pre-recorded instruction log.
"""

from collections import deque
from collections.abc import Callable

from .orders import Cancel, Instruction, Limit, Side
from .world import WARMUP

HALF_SPREAD = 2
QUOTE_SIZE = 2
INVENTORY_LIMIT = 20
SKEW_PER_UNIT = 0.2


class FixedQuotes:
    name = "fixed"

    def quotes(self, value: int, position: int) -> tuple[int, int]:
        return value - HALF_SPREAD, value + HALF_SPREAD


class InventorySkew:
    name = "skew"

    def quotes(self, value: int, position: int) -> tuple[int, int]:
        skew = round(SKEW_PER_UNIT * position)
        return value - HALF_SPREAD - skew, value + HALF_SPREAD - skew


STRATEGIES = (FixedQuotes(), InventorySkew())


class Ledger:
    """The market maker's cash, inventory, and per-order fills."""

    def __init__(self) -> None:
        self.cash = 0
        self.position = 0
        self.volume = 0
        self.maker_volume = 0
        self.size: dict[str, int] = {}
        self.filled: dict[str, int] = {}
        self.closed: set[str] = set()

    def register(self, order_id: str, quantity: int) -> None:
        self.size[order_id] = quantity
        self.filled[order_id] = 0

    def fill(self, order_id: str, side: Side, price: int, quantity: int, maker: bool) -> None:
        self.filled[order_id] += quantity
        assert self.filled[order_id] <= self.size[order_id], order_id
        sign = 1 if side is Side.BUY else -1
        self.position += sign * quantity
        self.cash -= sign * price * quantity
        self.volume += quantity
        if maker:
            self.maker_volume += quantity

    def close(self, order_id: str) -> None:
        self.closed.add(order_id)

    def is_open(self, order_id: str) -> bool:
        return (
            order_id in self.size
            and order_id not in self.closed
            and self.filled[order_id] < self.size[order_id]
        )


class Agent:
    def __init__(
        self,
        make_venue: Callable[[Ledger], object],
        strategy=None,
        delay: int = 0,
        trace: list[tuple[int, Instruction]] | None = None,
    ) -> None:
        self.ledger = Ledger()
        self.venue = make_venue(self.ledger)
        self.strategy = strategy
        self.delay = delay
        self.outbox: deque[tuple[int, Instruction]] = deque(trace or ())
        self.trace: list[tuple[int, Instruction]] = []
        self._quotes: dict[Side, tuple[str, int] | None] = {Side.BUY: None, Side.SELL: None}
        self._pending: set[str] = set()
        self._next_id = 0
        # Running statistics over post-warm-up steps.
        self.steps = 0
        self.limited_steps = 0
        self._sum_pos = 0
        self._sum_pos_sq = 0
        self.max_abs_position = 0
        self._peak = 0
        self.max_drawdown = 0

    def phase5(self, step: int, value: int) -> None:
        if self.strategy is not None and step > WARMUP:
            self._decide(step, value)
        self._deliver(step)
        if step > WARMUP:
            self._record(value)

    def _live(self, order_id: str) -> bool:
        return order_id in self._pending or self.ledger.is_open(order_id)

    def _decide(self, step: int, value: int) -> None:
        position = self.ledger.position
        bid, ask = self.strategy.quotes(value, position)
        want = {
            Side.BUY: bid if position + QUOTE_SIZE <= INVENTORY_LIMIT else None,
            Side.SELL: ask if position - QUOTE_SIZE >= -INVENTORY_LIMIT else None,
        }
        if None in want.values():
            self.limited_steps += 1

        cancels: list[Instruction] = []
        new: list[Instruction] = []
        for side in Side:
            current = self._quotes[side]
            live = current is not None and self._live(current[0])
            if live and current[1] == want[side]:
                continue  # unchanged quote keeps its queue position
            if live:
                cancels.append(Cancel(current[0]))
            self._quotes[side] = None
            if want[side] is not None:
                self._next_id += 1
                order_id = f"mm{self._next_id}"
                new.append(Limit(order_id, "mm", side, want[side], QUOTE_SIZE))
                self._quotes[side] = (order_id, want[side])
                self._pending.add(order_id)
        # Cancels go first so a new quote never meets the quote it replaces.
        for instruction in cancels + new:
            self.outbox.append((step + self.delay, instruction))

    def _deliver(self, step: int) -> None:
        while self.outbox and self.outbox[0][0] <= step:
            _, instruction = self.outbox.popleft()
            if isinstance(instruction, Limit):
                self._pending.discard(instruction.order_id)
            self.trace.append((step, instruction))
            self.venue.submit(instruction)

    def _record(self, value: int) -> None:
        position = self.ledger.position
        self.steps += 1
        self._sum_pos += position
        self._sum_pos_sq += position * position
        self.max_abs_position = max(self.max_abs_position, abs(position))
        equity = self.ledger.cash + position * value
        self._peak = max(self._peak, equity)
        self.max_drawdown = max(self.max_drawdown, self._peak - equity)

    def summary(self, final_value: int) -> dict:
        n = max(self.steps, 1)
        mean = self._sum_pos / n
        return {
            "pnl": self.ledger.cash + self.ledger.position * final_value,
            "position": self.ledger.position,
            "volume": self.ledger.volume,
            "maker_volume": self.ledger.maker_volume,
            "inventory_std": max(self._sum_pos_sq / n - mean * mean, 0.0) ** 0.5,
            "max_abs_position": self.max_abs_position,
            "max_drawdown": self.max_drawdown,
            "limited_fraction": self.limited_steps / n,
        }
