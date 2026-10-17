import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardcam.count import Shoe, count_log, true_count_spread
from cardcam.tracker import DEALER, extract, fill_dealer_blackjack

PLAYERS = ["Guan_Yu", "BraveLumina", "chrissyy5", "HonestOracle", "JubilantCapt", "FearlessInve"]
EVERYONE = PLAYERS + [DEALER]


def build_readings(steps, hold=4, dt=0.5):
    state = {name: "-" for name in EVERYONE}
    readings = []
    t = 0.0
    for _ in range(10):
        readings.append((t, dict(state)))
        t += dt
    for change in steps:
        state.update(change)
        for _ in range(hold):
            readings.append((t, dict(state)))
            t += dt
    return readings


def hands(events):
    out = {}
    for e in events:
        if e["kind"] == "card":
            out.setdefault(e["seat"], []).append(e["v"])
        if e["kind"] == "bust":
            out.setdefault(e["seat"], []).append(tuple(e["cands"]))
    return out


def anomalies(events):
    return [e for e in events if e["kind"] == "anomaly"]


CLEAR = [{name: "-" for name in EVERYONE}, {}, {}, {}]

REAL_ROUND = [
    {"FearlessInve": "10"},
    {"JubilantCapt": "10"},
    {"HonestOracle": "2"},
    {"chrissyy5": "1/11"},
    {"BraveLumina": "7"},
    {"Guan_Yu": "10"},
    {DEALER: "10"},
    {"FearlessInve": "13"},
    {"JubilantCapt": "13"},
    {"HonestOracle": "11"},
    {"chrissyy5": "BJ"},
    {"BraveLumina": "12"},
    {"Guan_Yu": "14"},
    {"HonestOracle": "DBL"},
    {"HonestOracle": "19"},
    {"JubilantCapt": "BUST"},
    {"Guan_Yu": "18"},
    {DEALER: "14"},
    {DEALER: "BUST"},
    {"chrissyy5": "END", "HonestOracle": "END", "JubilantCapt": "END"},
] + CLEAR


def test_real_round():
    events, rounds = extract(build_readings(REAL_ROUND), PLAYERS)
    events = fill_dealer_blackjack(events, rounds)
    assert anomalies(events) == []
    assert len(rounds) == 1
    assert hands(events) == {
        "FearlessInve": [10, 3],
        "JubilantCapt": [10, 3, (9, 10)],
        "HonestOracle": [2, 9, 8],
        "chrissyy5": [1, 10],
        "BraveLumina": [7, 5],
        "Guan_Yu": [10, 4, 4],
        DEALER: [10, 4, (8, 9, 10)],
    }


def test_flicker_ignored():
    steps = list(REAL_ROUND)
    steps.insert(8, {"BraveLumina": "-"})
    steps.insert(9, {"BraveLumina": "7"})
    events, _ = extract(build_readings(steps), PLAYERS)
    assert hands(events)["BraveLumina"] == [7, 5]


def test_dealer_blackjack():
    steps = [{"Guan_Yu": "10"}, {DEALER: "1/11"}, {"Guan_Yu": "17"},
             {"Guan_Yu": "END", DEALER: "-"}] + CLEAR
    events, rounds = extract(build_readings(steps), PLAYERS)
    events = fill_dealer_blackjack(events, rounds)
    assert hands(events)[DEALER] == [1, 10]
    assert anomalies(events) == []


def test_split():
    steps = [{"Guan_Yu": "8"}, {DEALER: "10"}, {"Guan_Yu": "16"},
             {"Guan_Yu": "8|8"}, {"Guan_Yu": "18|8"}, {"Guan_Yu": "18|11"},
             {DEALER: "17"}] + CLEAR
    events, _ = extract(build_readings(steps), PLAYERS)
    assert hands(events)["Guan_Yu"] == [8, 8, 10, 3]


def test_bust_adds_uncertainty():
    shoe = Shoe(8)
    for value in [2, 3, 4, 5, 6]:
        shoe.remove_card(value)
    assert shoe.running == 5
    shoe.apply({"kind": "bust", "cands": [9, 10]})
    assert 4 < shoe.running < 5
    assert shoe.true_count_sd() > 0


def test_spread_theory():
    assert 1.5 < true_count_spread(140) < 1.7
    assert 3.6 < true_count_spread(312) < 4.2


def test_shuffle_resets_count():
    events = [{"t": 1, "seat": "x", "kind": "card", "v": 5},
              {"t": 10, "seat": "x", "kind": "card", "v": 5}]
    rows = count_log(events, shuffles=[5])
    assert [r["shoe"] for r in rows] == [0, 1]
    assert [r["rc"] for r in rows] == [1, 1]


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            print("ok", name)
