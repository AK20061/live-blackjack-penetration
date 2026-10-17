import json
from pathlib import Path

import numpy as np

folder = Path(globals().get("MODEL_DIR", "models"))
folder.mkdir(parents=True, exist_ok=True)

char_images = np.asarray(CB, np.float32)
char_labels = np.asarray(CY)
badge_images = np.array([s.ravel() for s in seen], np.uint8)
np.savez_compressed(folder / "templates.npz", CB=char_images, CY=char_labels, SN=badge_images)

(folder / "badge_labels.json").write_text(json.dumps(blabels, indent=1))

seat_boxes = {}
for name, box in SEATS.items():
    seat_boxes[name] = [int(v) for v in box]
(folder / "seats.json").write_text(json.dumps(seat_boxes, indent=1))

print("wrote", folder)
for path in sorted(folder.iterdir()):
    print(" ", path.name)
