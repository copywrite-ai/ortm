# GStreamer integration

Install GStreamer, the `cairooverlay` plugin, PyGObject, and pycairo. Install the
ORTM Python package from the repository root, then place the integration module
on `PYTHONPATH`:

```bash
python3 -m pip install -e .
PYTHONPATH=integrations/gstreamer python3 examples/gstreamer_testsrc.py
```

The important pipeline order is:

```text
source -> raw video conversion -> cairooverlay -> encoder -> WebRTC/WHIP sink
```

Attach the renderer to a named `cairooverlay`:

```python
pipeline = Gst.parse_launch(
    "videotestsrc is-live=true "
    "! cairooverlay name=ortm_overlay "
    "! videoconvert ! x264enc tune=zerolatency "
    "! ..."
)
renderer = attach_to_pipeline(pipeline)
```

When using GStreamer's `whipclientsink`, configure its signaller endpoint and
request video pad according to the installed plugin version. ORTM does not own
the signaling or transport layer.

## Sparse rendering

The Cairo adapter can omit the background panel and outer border while retaining
the encoded finder, timing, and payload cells:

```python
renderer = OrtmCairoOverlay(
    background_alpha=0,
    cell_alpha=0.70,
    border_alpha=0,
)
```

This reduces visual obstruction, but also makes decoding more dependent on the
underlying video content and codec settings. Validate the selected geometry and
alpha against representative moving backgrounds before deployment.

On the experimental three-finder branch, omit the bottom-right finder with:

```python
renderer = OrtmCairoOverlay(
    background_alpha=0,
    cell_alpha=0.70,
    border_alpha=0,
    finder_layout="three",
)
```

The receiver must use the same finder layout. This mode preserves the ORTM v0
payload cells but is not compatible with a decoder that validates four finders.
