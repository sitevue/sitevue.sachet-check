"""Per-frame signals on synthetic frames."""
import numpy as np

from sachet_check import Config
from sachet_check.signals import FrameSignals

CFG = Config.load()


def _frame_with_drop_box(bgr):
    f = np.full((1080, 1920, 3), 120, np.uint8)            # grey steel everywhere
    x0, y0, x1, y1 = CFG["regions"]["drop"]
    f[y0 + 100:y1 - 50, x0 + 20:x1 - 20] = bgr              # a tray's meat under the chute
    return f


def test_pale_meat_under_film_counts_as_a_tray():
    """White-label product: pink meat seen through the film has saturation ~60, below the old floor of 70.
    The drop box must still see a tray (11-11 19:00-20:00)."""
    s = FrameSignals(CFG).compute(_frame_with_drop_box((180, 180, 235)))
    assert s["drop_meat"] > CFG["sets"]["meat_min"]


def test_grey_steel_is_not_a_tray():
    s = FrameSignals(CFG).compute(np.full((1080, 1920, 3), 120, np.uint8))
    assert s["drop_meat"] < CFG["sets"]["meat_min"]
