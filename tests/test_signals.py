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


def _frame_with_patch(bgr, box=(560, 420, 760, 600)):
    f = np.full((1080, 1920, 3), 120, np.uint8)
    x0, y0, x1, y1 = box
    f[y0:y1, x0:x1] = bgr
    return f


def test_blue_glove_beside_the_chute_is_seen():
    """Bright saturated blue (H ~100, S ~240, V ~220), 200 x 180 px beside the chute: a worker's glove."""
    s = FrameSignals(CFG).compute(_frame_with_patch((220, 151, 13)))
    assert s["glove"] > CFG["sets"]["glove_min"]


def test_dark_navy_steel_is_not_a_glove():
    s = FrameSignals(CFG).compute(_frame_with_patch((100, 60, 10)))
    assert s["glove"] < CFG["sets"]["glove_min"]


def test_the_blue_belt_itself_is_not_a_glove():
    x0, y0, x1, y1 = CFG["regions"]["belt"]
    s = FrameSignals(CFG).compute(_frame_with_patch((220, 151, 13), (x0, y0, x1, y1)))
    assert s["glove"] == 0.0
