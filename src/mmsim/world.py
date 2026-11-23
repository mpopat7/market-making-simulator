"""The synthetic background market from docs/EXPERIMENT.md, section 1.

A World owns one matching engine and runs phases 1-4 of every step. Phase 5,
the market maker's turn, belongs to whoever drives the world. Every event the
engine emits is passed to the world's observers as it happens, so a fill model
sees the book exactly as it was when each event occurred.
"""

import math
import random
from dataclasses import dataclass

from .engine import MatchingEngine
from .invariants import check_invariants
from .orders import Cancel, Event, Instruction, Limit, Market, Side

START_VALUE = 1000
WARMUP = 1000
STEPS = 20000
INVARIANT_EVERY = 1000


@dataclass(frozen=True)
class Params:
    p_jump: float = 0.02
    p_cancel: float = 0.02
    p_post: float = 0.6
    p_market: float = 0.3
    informed: float = 0.0


class World:
    def __init__(self, params: Params, seed: int) -> None:
        self.params = params
        self.engine = MatchingEngine()
        self.value = START_VALUE
        self.step = 0
        self.observers: list = []
        self.empty_side_steps = 0
        self._rng = {name: random.Random(f"{seed}:{name}") for name in ("value", "post", "taker")}
        self._expiry: dict[int, list[str]] = {}
        self._next_id = 0

    def send(self, instruction: Instruction) -> list[Event]:
        events = self.engine.submit(instruction)
        for observer in self.observers:
            observer.on_events(events, self)
        return events

    def advance(self) -> None:
        """Run phases 1-4 of the next step."""
        self.step += 1
        self._update_value()
        self._cancel_expired()
        self._post()
        self._take()

    def finish_step(self) -> None:
        """Bookkeeping after phase 5."""
        book = self.engine.book
        if self.step > WARMUP and (
            book.best_price(Side.BUY) is None or book.best_price(Side.SELL) is None
        ):
            self.empty_side_steps += 1
        if self.step % INVARIANT_EVERY == 0:
            check_invariants(self.engine)

    def _new_id(self, prefix: str) -> str:
        self._next_id += 1
        return f"{prefix}{self._next_id}"

    def _update_value(self) -> None:
        u = self._rng["value"].random()
        half = self.params.p_jump / 2
        if u < half:
            self.value += 1
        elif u < 2 * half:
            self.value -= 1

    def _cancel_expired(self) -> None:
        for order_id in self._expiry.pop(self.step, ()):
            if self.engine.orders[order_id].remaining > 0:
                self.send(Cancel(order_id))

    def _post(self) -> None:
        # Every draw is made every step, posted or not, so this stream stays
        # aligned between worlds that differ only in the market maker.
        rng, p = self._rng["post"], self.params
        posts = rng.random() < p.p_post
        side = Side.BUY if rng.random() < 0.5 else Side.SELL
        offset, growing = 1, True
        for _ in range(4):  # 1 + Geometric(0.5), capped at 5
            if rng.random() < 0.5 and growing:
                offset += 1
            else:
                growing = False
        size = rng.randint(1, 5)
        # Lifetime ~ Geometric(p_cancel): the same distribution as canceling
        # each resting order with probability p_cancel per step.
        lifetime = 1 + int(math.log(1.0 - rng.random()) / math.log(1.0 - p.p_cancel))
        if not posts:
            return

        price = self.value - offset if side is Side.BUY else self.value + offset
        opposite = self.engine.book.best_price(side.opposite)
        if opposite is not None and (price >= opposite if side is Side.BUY else price <= opposite):
            return  # post-only: never cross the book
        order_id = self._new_id("bg")
        self.send(Limit(order_id, "bg-lp", side, price, size))
        self._expiry.setdefault(self.step + lifetime, []).append(order_id)

    def _take(self) -> None:
        rng, p = self._rng["taker"], self.params
        takes = rng.random() < p.p_market
        size = rng.randint(1, 3)
        informed = rng.random() < p.informed
        side = Side.BUY if rng.random() < 0.5 else Side.SELL
        if not takes:
            return

        if informed:
            bid = self.engine.book.best_price(Side.BUY)
            ask = self.engine.book.best_price(Side.SELL)
            if ask is not None and ask < self.value:
                side = Side.BUY
            elif bid is not None and bid > self.value:
                side = Side.SELL
            else:
                return
        self.send(Market(self._new_id("bt"), "bg-taker", side, size))
