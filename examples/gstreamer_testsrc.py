#!/usr/bin/env python3
"""Display a GStreamer test source carrying ORTM v0."""

from __future__ import annotations

import argparse
import signal

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
from gi.repository import GLib, Gst

from ortm_overlay import OrtmCairoOverlay, attach_to_pipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--background-alpha", type=float, default=0.15)
    parser.add_argument("--cell-alpha", type=float, default=0.65)
    parser.add_argument("--border-alpha", type=float, default=1.0)
    parser.add_argument("--sink", default="autovideosink sync=false")
    args = parser.parse_args()

    Gst.init(None)
    pipeline = Gst.parse_launch(
        "videotestsrc is-live=true pattern=ball "
        f"! video/x-raw,width={args.width},height={args.height},framerate={args.fps}/1 "
        "! cairooverlay name=ortm_overlay "
        "! videoconvert "
        f"! {args.sink}"
    )

    def report(frame) -> None:
        if frame.frame_seq % max(args.fps, 1) == 0:
            print(
                f"ORTM seq={frame.frame_seq} timestamp_ms={frame.timestamp_ms} "
                f"pts_ns={frame.pts_ns} render_ms={frame.render_ms:.3f}",
                flush=True,
            )

    attach_to_pipeline(
        pipeline,
        renderer=OrtmCairoOverlay(
            background_alpha=args.background_alpha,
            cell_alpha=args.cell_alpha,
            border_alpha=args.border_alpha,
            on_rendered=report,
        ),
    )
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()

    def on_message(_bus, message) -> None:
        if message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            print(f"GStreamer error: {error}; {debug or ''}", flush=True)
            loop.quit()
        elif message.type == Gst.MessageType.EOS:
            loop.quit()

    bus.connect("message", on_message)
    signal.signal(signal.SIGINT, lambda *_args: loop.quit())
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    finally:
        pipeline.set_state(Gst.State.NULL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
