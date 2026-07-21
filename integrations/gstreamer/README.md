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
