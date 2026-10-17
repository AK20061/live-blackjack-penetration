import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardcam.badges import BadgeReader
from cardcam.count import count_log, save_csv, shoe_summary
from cardcam.tracker import DEALER, extract, fill_dealer_blackjack
from cardcam.video import frames_from_video


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--shuffles", type=float, nargs="*", default=[])
    parser.add_argument("--decks", type=int, default=8)
    parser.add_argument("--models", default="models")
    parser.add_argument("--every", type=float, default=0.5)
    return parser.parse_args()


def read_video(reader, path, every, cache):
    if cache.exists():
        readings = json.loads(cache.read_text())
        print("loaded", len(readings), "cached readings")
        return readings
    names = reader.players + [DEALER]
    readings = []
    start = time.time()
    for t, frame in frames_from_video(path, every):
        readings.append((t, reader.read_all(frame, names)))
    cache.write_text(json.dumps(readings))
    print("read", len(readings), "samples in", round(time.time() - start), "s")
    return readings


def count_kinds(events):
    kinds = {"card": 0, "bust": 0, "pair": 0, "anomaly": 0}
    for e in events:
        kinds[e["kind"]] += 1
    return kinds


def print_rounds(events, rounds):
    edges = [0] + rounds + [1e9]
    for number, (start, end) in enumerate(zip(edges[:-1], edges[1:])):
        hands = {}
        for e in events:
            if start <= e["t"] < end and e["kind"] in ("card", "bust", "pair"):
                hands.setdefault(e["seat"], []).append(e)
        if not hands:
            continue
        print("round", number)
        for seat, cards in hands.items():
            shown = []
            for e in cards:
                if e["kind"] == "card":
                    shown.append("A" if e["v"] == 1 else "T" if e["v"] == 10 else str(e["v"]))
                elif e["kind"] == "bust":
                    shown.append("[" + "/".join(str(v) for v in e["cands"]) + "]")
                else:
                    shown.append("(pair " + str(e["L"]) + ")")
            print("  ", seat, " ".join(shown))


def main():
    args = parse_args()
    out = Path("output")
    out.mkdir(exist_ok=True)
    name = Path(args.video).stem

    reader = BadgeReader(args.models)
    readings = read_video(reader, args.video, args.every, out / f"readings_{name}.json")

    events, rounds = extract(readings, reader.players)
    events = fill_dealer_blackjack(events, rounds)

    kinds = count_kinds(events)
    print("rounds", len(rounds))
    print("cards", kinds["card"], "busts", kinds["bust"], "pairs", kinds["pair"], "anomalies", kinds["anomaly"])
    for e in events:
        if e["kind"] == "anomaly":
            print("anomaly", round(e["t"]), e["seat"], e["note"])

    print_rounds(events, rounds)

    rows = count_log(events, args.shuffles, args.decks)
    save_csv(rows, out / f"count_log_{name}.csv")

    summary = shoe_summary(rows, args.decks)
    save_csv(summary, out / f"shoes_{name}.csv")
    print("shoe start end cards pen tc_end tc_min tc_max sd_end")
    for s in summary:
        print(s["shoe"], s["start"], s["end"], s["cards"], s["pen"],
              s["tc_end"], s["tc_min"], s["tc_max"], s["sd_end"])


if __name__ == "__main__":
    main()
