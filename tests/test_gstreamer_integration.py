from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ortm.codec import ENCODED_CELLS

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "integrations" / "gstreamer" / "ortm_overlay.py"


class FakeContext:
    def __init__(self) -> None:
        self.rectangles = []
        self.antialias = None

    def save(self):
        pass

    def restore(self):
        pass

    def set_antialias(self, value):
        self.antialias = value

    def set_source_rgba(self, *_args):
        pass

    def set_source_rgb(self, *_args):
        pass

    def set_line_width(self, *_args):
        pass

    def rectangle(self, *args):
        self.rectangles.append(args)

    def fill(self):
        pass

    def stroke(self):
        pass


def load_adapter():
    fake_gi = types.ModuleType("gi")
    fake_gi.require_foreign = lambda *_args: None
    fake_gi.require_version = lambda *_args: None
    fake_cairo = types.ModuleType("cairo")
    fake_cairo.ANTIALIAS_NONE = 1
    fake_gst = types.SimpleNamespace(CLOCK_TIME_NONE=-1)
    fake_repository = types.ModuleType("gi.repository")
    fake_repository.Gst = fake_gst
    spec = importlib.util.spec_from_file_location("ortm_overlay_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {"gi": fake_gi, "cairo": fake_cairo, "gi.repository": fake_repository},
    ):
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return module


class GStreamerAdapterTest(unittest.TestCase):
    def test_draw_uses_reference_grid_and_emits_frame_identity(self) -> None:
        adapter = load_adapter()
        rendered = []
        renderer = adapter.OrtmCairoOverlay(
            clock_ms=lambda: 0x12345678,
            on_rendered=rendered.append,
        )
        context = FakeContext()
        renderer.draw(None, context, 987654321, None)

        self.assertEqual(context.antialias, 1)
        self.assertEqual(len(context.rectangles), len(ENCODED_CELLS) + 2)
        self.assertEqual(rendered[0].frame_seq, 0)
        self.assertEqual(rendered[0].timestamp_ms, 0x12345678)
        self.assertEqual(rendered[0].pts_ns, 987654321)
        self.assertGreaterEqual(rendered[0].render_ms, 0)

        renderer.draw(None, FakeContext(), -1, None)
        self.assertEqual(rendered[1].frame_seq, 1)
        self.assertIsNone(rendered[1].pts_ns)


if __name__ == "__main__":
    unittest.main()
