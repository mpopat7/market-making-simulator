"""Resting orders, grouped by side and price level.

Each price level is a FIFO queue. Arrival order inside a level is time
priority, so a partially filled order stays at the front of its queue.
Best-price lookup scans the level keys, which is fine at this size.
"""

from collections import deque

from .orders import Order, Side


class OrderBook:
    def __init__(self) -> None:
        self._levels: dict[Side, dict[int, deque[Order]]] = {Side.BUY: {}, Side.SELL: {}}

    def best_price(self, side: Side) -> int | None:
        levels = self._levels[side]
        if not levels:
            return None
        return max(levels) if side is Side.BUY else min(levels)

    def best_order(self, side: Side) -> Order | None:
        price = self.best_price(side)
        if price is None:
            return None
        return self._levels[side][price][0]

    def add(self, order: Order) -> None:
        assert order.price is not None and order.remaining > 0
        self._levels[order.side].setdefault(order.price, deque()).append(order)

    def remove(self, order: Order) -> None:
        level = self._levels[order.side][order.price]
        level.remove(order)
        if not level:
            del self._levels[order.side][order.price]

    def level(self, side: Side, price: int) -> tuple[Order, ...]:
        """Resting orders at one price, in time priority. Empty if none."""
        return tuple(self._levels[side].get(price, ()))

    def orders(self, side: Side) -> list[Order]:
        """Resting orders on one side, best price first, then time priority."""
        levels = self._levels[side]
        prices = sorted(levels, reverse=side is Side.BUY)
        return [order for price in prices for order in levels[price]]

    def snapshot(self) -> dict[str, list[tuple[int, list[tuple[str, int]]]]]:
        """Bids and asks as (price, [(order_id, remaining), ...]), best first."""
        result = {}
        for name, side in (("bids", Side.BUY), ("asks", Side.SELL)):
            levels = self._levels[side]
            prices = sorted(levels, reverse=side is Side.BUY)
            result[name] = [
                (price, [(o.order_id, o.remaining) for o in levels[price]]) for price in prices
            ]
        return result
