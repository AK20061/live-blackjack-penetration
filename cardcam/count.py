import csv
import math

HILO = {1: -1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 0, 8: 0, 9: 0, 10: -1}
HILO_VARIANCE = 0.769


def fresh_shoe(decks):
    shoe = {}
    for value in range(1, 10):
        shoe[value] = 4 * decks
    shoe[10] = 16 * decks
    return shoe


def pair_options(shoe, total):
    options = []
    for a in range(1, 11):
        b = total - a
        if b < a or b > 10:
            continue
        if a == b:
            weight = shoe[a] * (shoe[a] - 1)
        else:
            weight = shoe[a] * shoe[b]
        options.append(((a, b), weight))
    return options


def bust_options(shoe, candidates):
    return [((v,), shoe[v]) for v in candidates]


class Shoe:
    def __init__(self, decks=8):
        self.decks = decks
        self.reset()

    def reset(self):
        self.cards = fresh_shoe(self.decks)
        self.running = 0.0
        self.variance = 0.0

    def remaining(self):
        return sum(self.cards.values())

    def decks_left(self):
        return self.remaining() / 52

    def dealt(self):
        return 52 * self.decks - self.remaining()

    def remove_card(self, value):
        self.cards[value] -= 1
        self.running += HILO[value]

    def remove_uncertain(self, options):
        total_weight = sum(w for _, w in options)
        mean = 0.0
        mean_square = 0.0
        for values, weight in options:
            p = weight / total_weight
            tag = sum(HILO[v] for v in values)
            for v in values:
                self.cards[v] -= p
            mean += p * tag
            mean_square += p * tag * tag
        self.running += mean
        self.variance += mean_square - mean * mean

    def apply(self, event):
        if event["kind"] == "card":
            self.remove_card(event["v"])
        elif event["kind"] == "bust":
            self.remove_uncertain(bust_options(self.cards, event["cands"]))
        elif event["kind"] == "pair":
            self.remove_uncertain(pair_options(self.cards, event["L"]))
        else:
            return False
        return True

    def true_count(self):
        return self.running / self.decks_left()

    def true_count_sd(self):
        return math.sqrt(self.variance) / self.decks_left()

    def penetration(self):
        return self.dealt() / (52 * self.decks)


def describe(event):
    if event["kind"] == "card":
        return event["v"]
    if event["kind"] == "bust":
        return "/".join(str(v) for v in event["cands"])
    return "pair" + str(event["L"])


def count_log(events, shuffles=(), decks=8):
    shoe = Shoe(decks)
    shuffles = sorted(shuffles)
    rows = []
    shoe_number = 0
    next_shuffle = 0
    for event in sorted(events, key=lambda e: e["t"]):
        while next_shuffle < len(shuffles) and event["t"] >= shuffles[next_shuffle]:
            shoe.reset()
            shoe_number += 1
            next_shuffle += 1
        if not shoe.apply(event):
            continue
        rows.append({
            "shoe": shoe_number,
            "t": round(event["t"], 1),
            "seat": event["seat"],
            "kind": event["kind"],
            "card": describe(event),
            "rc": round(shoe.running, 2),
            "tc": round(shoe.true_count(), 2),
            "tc_sd": round(shoe.true_count_sd(), 2),
            "pen": round(shoe.penetration(), 3),
        })
    return rows


def shoe_summary(rows, decks=8):
    shoes = {}
    for row in rows:
        shoes.setdefault(row["shoe"], []).append(row)
    summary = []
    for number in sorted(shoes):
        cards = shoes[number]
        counts = [r["tc"] for r in cards]
        summary.append({
            "shoe": number,
            "start": cards[0]["t"],
            "end": cards[-1]["t"],
            "cards": len(cards),
            "pen": round(len(cards) / (52 * decks), 3),
            "tc_end": cards[-1]["tc"],
            "tc_min": min(counts),
            "tc_max": max(counts),
            "sd_end": cards[-1]["tc_sd"],
        })
    return summary


def save_csv(rows, path):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def true_count_spread(cards_dealt, decks=8):
    total = 52 * decks
    left = total - cards_dealt
    running_sd = math.sqrt(cards_dealt * HILO_VARIANCE * left / (total - 1))
    return running_sd / (left / 52)
