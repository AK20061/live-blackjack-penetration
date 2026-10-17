from .badges import low_total

DEALER = "dealer_centre"


def card(t, seat, value):
    return {"t": t, "seat": seat, "kind": "card", "v": value}


def bust(t, seat, low):
    smallest = max(2, 22 - low)
    return {"t": t, "seat": seat, "kind": "bust", "cands": list(range(smallest, 11))}


def pair(t, seat, total):
    return {"t": t, "seat": seat, "kind": "pair", "L": total}


def anomaly(t, seat, note):
    return {"t": t, "seat": seat, "kind": "anomaly", "note": note}


class Seat:
    def __init__(self, name, confirm=3, blank_reset=8):
        self.name = name
        self.confirm = confirm
        self.blank_reset = blank_reset
        self.pending = None
        self.seen = 0
        self.blanks = 0
        self.new_hand()

    def new_hand(self):
        self.low = None
        self.done = False
        self.cards = 0
        self.active = False
        self.ace = False
        self.busted = False

    def best_total(self):
        if self.low is None:
            return None
        if self.ace and self.low + 10 <= 21:
            return self.low + 10
        return self.low

    def handle_blank(self, t, events, allow_reset):
        self.blanks += 1
        if self.blanks < self.blank_reset:
            return
        if not allow_reset and self.active:
            return
        if self.active:
            if self.cards < 2:
                events.append(anomaly(t, self.name, f"only {self.cards} card(s)"))
            events.append({"t": t, "seat": self.name, "kind": "reset",
                           "best": self.best_total(), "bust": self.busted})
        self.new_hand()

    def is_confirmed(self, reading):
        if reading != self.pending:
            self.pending = reading
            self.seen = 1
            return False
        self.seen += 1
        return self.seen == self.confirm

    def handle_bust(self, t, events):
        if self.low is not None:
            events.append(bust(t, self.name, self.low))
            self.cards += 1
        self.done = True
        self.busted = True

    def handle_blackjack(self, t, events):
        if self.low is None:
            missing = [1, 10]
        elif self.low == 1:
            missing = [10]
        elif self.low == 10:
            missing = [1]
        else:
            missing = []
            events.append(anomaly(t, self.name, f"BJ from {self.low}"))
        for value in missing:
            events.append(card(t, self.name, value))
        self.cards += len(missing)
        self.low = 11
        self.ace = True
        self.done = True

    def handle_total(self, t, reading, events):
        total = low_total(reading)
        if total is None:
            return
        if "/" in reading:
            self.ace = True
        if self.low is None:
            jump = total
        else:
            jump = total - self.low
        if 1 <= jump <= 10:
            events.append(card(t, self.name, jump))
            self.cards += 1
            if jump == 1:
                self.ace = True
        elif jump > 10:
            events.append(pair(t, self.name, jump))
            self.cards += 2
        self.low = total

    def update(self, t, reading, events, allow_reset=True):
        if reading == "-":
            self.handle_blank(t, events, allow_reset)
            return
        self.blanks = 0
        if reading == "?":
            return
        if not self.is_confirmed(reading):
            return
        if self.done:
            return
        if reading == "END":
            self.done = True
            return
        if reading == "DBL":
            return
        self.active = True
        if reading == "BUST":
            self.handle_bust(t, events)
        elif reading == "BJ":
            self.handle_blackjack(t, events)
        else:
            self.handle_total(t, reading, events)


def extract(readings, players, dealer=DEALER):
    seats = [Seat(name) for name in players]
    dealer_seat = Seat(dealer, confirm=2)
    events = []
    for t, reading in readings:
        dealer_seat.update(t, reading[dealer], events)
        for seat in seats:
            seat.update(t, reading[seat.name], events, allow_reset=not dealer_seat.active)

    rounds = []
    checks = []
    for e in events:
        if e["kind"] == "reset" and e["seat"] == dealer:
            rounds.append(e["t"])
            if not e["bust"] and (e["best"] or 0) < 17:
                checks.append(anomaly(e["t"], dealer, f"dealer stopped on {e['best']}"))

    kept = [e for e in events if e["kind"] != "reset"]
    return kept + checks, rounds


def events_between(events, start, end, seat):
    found = []
    for e in events:
        if start <= e["t"] < end and e["seat"] == seat and e["kind"] in ("card", "bust", "pair"):
            found.append(e)
    return found


def fill_dealer_blackjack(events, rounds, dealer=DEALER):
    events = list(events)
    edges = [0] + list(rounds) + [1e9]
    for start, end in zip(edges[:-1], edges[1:]):
        dealer_cards = events_between(events, start, end, dealer)
        if len(dealer_cards) != 1:
            continue
        up = dealer_cards[0]
        if up["kind"] != "card" or up["v"] not in (1, 10):
            continue
        events.append(card(up["t"] + 0.1, dealer, 11 - up["v"]))
        events = [e for e in events
                  if not (e["kind"] == "anomaly" and e["seat"] == dealer and start <= e["t"] <= end)]
    events.sort(key=lambda e: e["t"])
    return events
