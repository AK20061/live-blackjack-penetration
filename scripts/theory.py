import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardcam.count import true_count_spread

print("penetration cards_dealt tc_sd_at_shuffle")
for pen in [0.25, 0.34, 0.40, 0.50, 0.60, 0.65, 0.75, 0.80]:
    dealt = round(pen * 416)
    print(pen, dealt, round(true_count_spread(dealt), 2))
