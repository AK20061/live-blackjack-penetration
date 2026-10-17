import json
import threading
import time

from .count import Shoe, save_csv
from .tracker import DEALER, Seat


class LiveCounter:
    def __init__(self, reader, decks=8, log_path="live_log.csv"):
        self.reader = reader
        self.log_path = log_path
        self.lock = threading.Lock()
        self.shoe = Shoe(decks)
        self.rows = []
        self.shoe_starts = []
        self.running = False
        self.t = 0.0
        self.shoe_number = -1
        self.new_shoe()

    def new_shoe(self):
        with self.lock:
            self.shoe.reset()
            self.players = [Seat(name) for name in self.reader.players]
            self.dealer = Seat(DEALER, confirm=2)
            self.shoe_number += 1
            self.shoe_starts.append(self.t)
            with open("shoe_starts.json", "w") as f:
                json.dump(self.shoe_starts, f)
        print("new shoe", self.shoe_number, "at", round(self.t), "s")

    def step(self, t, frame):
        names = [seat.name for seat in self.players] + [DEALER]
        reading = self.reader.read_all(frame, names)
        events = []
        with self.lock:
            self.t = t
            self.dealer.update(t, reading[DEALER], events)
            for seat in self.players:
                seat.update(t, reading[seat.name], events, allow_reset=not self.dealer.active)
            for event in events:
                if self.shoe.apply(event):
                    self.rows.append({
                        "shoe": self.shoe_number,
                        "t": round(t, 1),
                        "seat": event["seat"],
                        "kind": event["kind"],
                        "rc": round(self.shoe.running, 2),
                        "tc": round(self.shoe.true_count(), 2),
                        "tc_sd": round(self.shoe.true_count_sd(), 2),
                        "pen": round(self.shoe.penetration(), 3),
                    })

    def status(self):
        with self.lock:
            return ("shoe " + str(self.shoe_number)
                    + " | t " + str(round(self.t))
                    + " | cards " + str(round(self.shoe.dealt()))
                    + " | pen " + str(round(self.shoe.penetration(), 3))
                    + " | rc " + str(round(self.shoe.running, 1))
                    + " | tc " + str(round(self.shoe.true_count(), 2))
                    + " +- " + str(round(self.shoe.true_count_sd(), 2)))

    def run(self, frames):
        self.running = True
        for t, frame in frames:
            if not self.running:
                break
            self.step(t, frame)
        self.running = False
        save_csv(self.rows, self.log_path)
        print("stopped, saved", len(self.rows), "rows to", self.log_path)


def notebook_ui(counter, frames):
    import ipywidgets as widgets
    from IPython.display import display

    new_shoe_button = widgets.Button(description="New shoe (reshuffle)", button_style="warning")
    stop_button = widgets.Button(description="Stop", button_style="danger")
    status = widgets.Label(counter.status())

    def on_new_shoe(_):
        counter.new_shoe()

    def on_stop(_):
        counter.running = False

    new_shoe_button.on_click(on_new_shoe)
    stop_button.on_click(on_stop)
    display(widgets.HBox([new_shoe_button, stop_button]), status)

    def refresh():
        while True:
            status.value = counter.status()
            if not counter.running and counter.t > 0:
                status.value += " | stopped"
                break
            time.sleep(1)

    threading.Thread(target=counter.run, args=(frames,), daemon=True).start()
    threading.Thread(target=refresh, daemon=True).start()
