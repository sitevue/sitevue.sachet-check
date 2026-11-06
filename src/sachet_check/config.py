"""Line/camera settings from a YAML file (configs/fpl-grind-04.yaml)."""
from __future__ import annotations

import copy
import os

import yaml

DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "..", "..", "configs", "fpl-grind-04.yaml")


class Config(dict):
    """The YAML as a dict, plus `frames(seconds)` once the stream frame rate is known."""

    @classmethod
    def load(cls, path: str | None = None) -> "Config":
        path = path or os.environ.get("SACHET_CONFIG") or DEFAULT_CONFIG
        with open(path) as f:
            c = cls(yaml.safe_load(f))
        c["_path"] = os.path.abspath(path)
        return c

    def with_fps(self, fps: float | None) -> "Config":
        c = Config(copy.deepcopy(dict(self)))
        c["fps"] = float(fps) if fps and 1 <= fps <= 120 else float(self["fps"])
        return c

    @property
    def fps(self) -> float:
        return float(self["fps"])

    def frames(self, seconds: float) -> int:
        """Seconds -> whole frames at this config's frame rate (0.3 s at 10 fps = 3 frames)."""
        return int(round(seconds * self.fps))

    def public(self) -> dict:
        return {k: v for k, v in self.items() if not k.startswith("_")}
