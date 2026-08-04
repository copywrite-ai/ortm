"""Reusable cairooverlay adapter for ORTM v0."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import gi

gi.require_foreign("cairo")
gi.require_version("Gst", "1.0")
import cairo
from gi.repository import Gst

from ortm.codec import ENCODED_CELLS, GRID_SIZE, encode_grid

DEFAULT_BACKGROUND_ALPHA = 0.15
DEFAULT_CELL_ALPHA = 0.65
DEFAULT_BORDER_ALPHA = 1.0


@dataclass(frozen=True)
class RenderedFrame:
    frame_seq: int
    timestamp_ms: int
    pts_ns: int | None
    render_ms: float


class OrtmCairoOverlay:
    """Draw ORTM immediately before encoding in a GStreamer pipeline."""

    def __init__(
        self,
        *,
        x: int = 24,
        y: int = 24,
        cell: int = 12,
        padding: int = 12,
        background_alpha: float = DEFAULT_BACKGROUND_ALPHA,
        cell_alpha: float = DEFAULT_CELL_ALPHA,
        border_alpha: float = DEFAULT_BORDER_ALPHA,
        initial_frame_seq: int = 0,
        clock_ms: Callable[[], int] | None = None,
        on_rendered: Callable[[RenderedFrame], None] | None = None,
    ) -> None:
        self.x = x
        self.y = y
        self.cell = cell
        self.padding = padding
        self.background_alpha = min(max(background_alpha, 0.0), 1.0)
        self.cell_alpha = min(max(cell_alpha, 0.0), 1.0)
        self.border_alpha = min(max(border_alpha, 0.0), 1.0)
        self.frame_seq = initial_frame_seq & 0xFFFF
        self.clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self.on_rendered = on_rendered

    @property
    def box_size(self) -> int:
        return GRID_SIZE * self.cell + self.padding * 2

    def draw(self, _overlay, context, timestamp, _duration) -> None:
        started_ns = time.monotonic_ns()
        frame_seq = self.frame_seq
        self.frame_seq = (self.frame_seq + 1) & 0xFFFF
        timestamp_ms = self.clock_ms()
        grid = encode_grid(frame_seq, timestamp_ms & 0xFFFFFFFF)

        context.save()
        try:
            context.set_antialias(cairo.ANTIALIAS_NONE)
            if self.background_alpha > 0:
                context.set_source_rgba(1, 1, 1, self.background_alpha)
                context.rectangle(self.x, self.y, self.box_size, self.box_size)
                context.fill()

            origin_x = self.x + self.padding
            origin_y = self.y + self.padding
            for bit, color in ((0, 1.0), (1, 0.0)):
                context.set_source_rgba(color, color, color, self.cell_alpha)
                for row, col in ENCODED_CELLS:
                    if grid[row][col] != bit:
                        continue
                    context.rectangle(
                        origin_x + col * self.cell,
                        origin_y + row * self.cell,
                        self.cell,
                        self.cell,
                    )
                context.fill()

            if self.border_alpha > 0:
                context.set_source_rgba(0, 0, 0, self.border_alpha)
                context.set_line_width(2)
                context.rectangle(self.x, self.y, self.box_size, self.box_size)
                context.stroke()
        finally:
            context.restore()

        if self.on_rendered:
            pts_ns = None if int(timestamp) == Gst.CLOCK_TIME_NONE else int(timestamp)
            self.on_rendered(
                RenderedFrame(
                    frame_seq=frame_seq,
                    timestamp_ms=timestamp_ms,
                    pts_ns=pts_ns,
                    render_ms=(time.monotonic_ns() - started_ns) / 1_000_000,
                )
            )

    def attach(self, overlay_element) -> None:
        overlay_element.connect("draw", self.draw)


def attach_to_pipeline(
    pipeline,
    *,
    element_name: str = "ortm_overlay",
    renderer: OrtmCairoOverlay | None = None,
) -> OrtmCairoOverlay:
    overlay = pipeline.get_by_name(element_name)
    if overlay is None:
        raise ValueError(f"pipeline has no cairooverlay named {element_name!r}")
    active_renderer = renderer or OrtmCairoOverlay()
    active_renderer.attach(overlay)
    return active_renderer
