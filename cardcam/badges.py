import json
import re
from pathlib import Path

import cv2
import numpy as np

ICONS = ["-", "BUST", "DBL", "END"]


def crop(frame, box):
    x, y, w, h = box
    x = max(0, x)
    return frame[y:y + h, x:x + w]


def upscale(image, factor):
    return cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)


def brightness(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return hsv[..., 2]


def dark_mask(v):
    return ((v < 90) * 255).astype(np.uint8)


def largest_pill(v):
    dark = dark_mask(v)
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    pill = np.zeros_like(dark)
    if contours:
        biggest = max(contours, key=cv2.contourArea)
        cv2.drawContours(pill, [biggest], -1, 255, -1)
    return pill


def white_inside(v, pill):
    text = (v > 170) & (pill > 0)
    return text.astype(np.uint8) * 255


def pill_is_empty(pill):
    return (pill > 0).mean() < 0.25


def text_mask(frame, box):
    v = brightness(upscale(crop(frame, box), 3))
    pill = largest_pill(v)
    if pill_is_empty(pill):
        return None
    return white_inside(v, pill)


def badge_pattern(frame, box):
    v = brightness(crop(frame, box))
    pill = largest_pill(v)
    text = white_inside(v, pill)
    if pill_is_empty(pill):
        text[:] = 0
    small = cv2.resize(text, (32, 24), interpolation=cv2.INTER_AREA)
    return (small > 100).astype(np.uint8)


def normalise_character(mask):
    h, w = mask.shape
    new_w = int(round(w * 24 / h))
    new_w = max(1, min(16, new_w))
    resized = cv2.resize(mask, (new_w, 24), interpolation=cv2.INTER_AREA)
    out = np.zeros((24, 16), np.uint8)
    left = (16 - new_w) // 2
    out[:, left:left + new_w] = resized
    return out


def split_characters(text):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(text, 8)
    height = text.shape[0]
    pieces = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if h > 0.3 * height and area > 15:
            pieces.append((x, i))
    pieces.sort()
    chars = []
    for x, i in pieces:
        bx, by, bw, bh, _ = stats[i]
        piece = labels[by:by + bh, bx:bx + bw] == i
        chars.append(normalise_character(piece.astype(np.uint8) * 255))
    return chars


def is_valid_total(s):
    if re.fullmatch(r"\d{1,2}", s):
        return 2 <= int(s) <= 21
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", s)
    if m is None:
        return False
    return int(m[2]) == int(m[1]) + 10


def low_of_one_hand(s):
    if re.fullmatch(r"\d{1,2}", s):
        return int(s)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", s)
    if m is None:
        return None
    return int(m[1])


def low_total(reading):
    total = 0
    for hand in reading.split("|"):
        low = low_of_one_hand(hand)
        if low is None:
            return None
        total += low
    return total


class BadgeReader:
    def __init__(self, folder="models"):
        folder = Path(folder)
        saved = np.load(folder / "templates.npz")
        self.char_images = saved["CB"].astype(np.float32)
        self.char_labels = saved["CY"]
        self.badge_images = saved["SN"].astype(np.float32)
        self.badge_labels = json.loads((folder / "badge_labels.json").read_text())
        seats = json.loads((folder / "seats.json").read_text())
        self.seats = {name: tuple(box) for name, box in seats.items()}
        self.players = [name for name in self.seats if not name.startswith("dealer")]
        self.wide_boxes = {}
        for name in self.players:
            x, y, w, h = self.seats[name]
            self.wide_boxes[name] = (int(x - 0.8 * w), y, int(2.6 * w), h)

    def nearest_character(self, char):
        flat = char.ravel() / 255.0
        distances = np.linalg.norm(self.char_images - flat, axis=1)
        return self.char_labels[distances.argmin()]

    def read_text(self, text):
        s = ""
        for char in split_characters(text):
            s += self.nearest_character(char)
        return s

    def read_icon(self, frame, box):
        pattern = badge_pattern(frame, box).ravel().astype(np.float32)
        distances = pattern.sum() + self.badge_images.sum(1) - 2 * self.badge_images @ pattern
        best = int(distances.argmin())
        label = self.badge_labels.get(str(best), "?")
        if label in ICONS and distances[best] <= 40:
            return label
        return None

    def read_badge(self, frame, box):
        text = text_mask(frame, box)
        if text is None:
            return "-"
        icon = self.read_icon(frame, box)
        if icon is not None:
            return icon
        s = self.read_text(text)
        if is_valid_total(s):
            return s
        if s == "BJ":
            return "BJ"
        return "?"

    def read_split(self, frame, name):
        v = brightness(upscale(crop(frame, self.wide_boxes[name]), 3))
        dark = dark_mask(v)
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        pills = [c for c in contours if cv2.contourArea(c) > 0.05 * dark.size]
        pills.sort(key=lambda c: cv2.boundingRect(c)[0])
        totals = []
        for c in pills:
            pill = np.zeros_like(dark)
            cv2.drawContours(pill, [c], -1, 255, -1)
            s = self.read_text(white_inside(v, pill))
            if is_valid_total(s):
                totals.append(s)
        return totals

    def read_seat(self, frame, name):
        reading = self.read_badge(frame, self.seats[name])
        if reading != "?" or name not in self.wide_boxes:
            return reading
        totals = self.read_split(frame, name)
        if len(totals) >= 2:
            return "|".join(totals)
        if len(totals) == 1:
            return totals[0]
        return "?"

    def read_all(self, frame, names=None):
        if names is None:
            names = list(self.seats)
        readings = {}
        for name in names:
            readings[name] = self.read_seat(frame, name)
        return readings
