# ORTM v0 GStreamer 发送端兼容指南

本文面向远端视频发送端。目标是让发送端生成的 ORTM 可以被已经验证过的固定 ROI Viewer 解码，而不要求 Viewer 修改候选尺度或位置规则。

## 固定兼容配置

双方必须锁定同一个仓库版本，并使用：

```text
profiles/ortm-v0-fixed-720p.json
```

关键参数如下：

```text
最终视频帧：1280x720
ORTM：32x32 grid
x=24
y=24
cell=12
padding=12
boxSize=408
背景 alpha=0.15
单元 alpha=0.65
抗锯齿：关闭
边框：2 px，不透明黑色
```

盒子在最终视频帧中的范围为 `[24, 432) x [24, 432)`。

## 必须遵守的管线顺序

ORTM 必须绘制在最终分辨率的原始视频帧上，并且位于编码器之前：

```text
camera
-> videoconvert
-> crop / videoscale / aspect-ratio processing
-> video/x-raw,width=1280,height=720
-> cairooverlay name=ortm_overlay
-> videoconvert
-> x264enc
-> WebRTC / WHIP
```

禁止采用：

```text
在 1920x1080 上绘制
-> 缩放到 1280x720
-> 编码
```

也不要在 ORTM 后面再做缩放、裁剪、补黑边、转码或宽高比调整。这些操作会改变固定 ROI 中的单元尺寸和位置。

## 使用参考 GStreamer adapter

安装 Python 包和图像校验依赖：

```bash
python3 -m pip install -e '.[image]'
```

确保 `integrations/gstreamer` 在 `PYTHONPATH` 中，然后复用：

```python
from ortm_overlay import OrtmCairoOverlay, attach_to_pipeline

renderer = OrtmCairoOverlay(
    x=24,
    y=24,
    cell=12,
    padding=12,
    background_alpha=0.15,
    cell_alpha=0.65,
)
attach_to_pipeline(pipeline, renderer=renderer)
```

`frame_seq` 每个绘制帧递增一次。`timestamp_ms` 使用发送端 Unix wall clock 毫秒的低 32 位。发送端时钟应与其 `/api/clock-sync` 接口代表同一个系统时钟。

`whipclientsink` 的 endpoint 属于 signaller：

```text
signaller::whip-endpoint="https://example.test/fish_front/whip"
```

ORTM 不负责 WebRTC 信令、ICE 或 TURN 配置。

## 编码前单帧验收

在接入 WHIP 前，从 `cairooverlay` 后、编码器前保存一张最终 `1280x720` 帧，例如 `final-frame.png`，然后执行：

```bash
python3 tools/validate_frame.py \
  --profile profiles/ortm-v0-fixed-720p.json \
  --input final-frame.png
```

成功结果类似：

```text
PASS
profile: ortm-v0-fixed-720p
resolution: 1280x720
version: 0
frame_seq: 1234
timestamp_ms: 2309737967
finder_errors: 0
timing_errors: 0
crc: valid
```

也可以生成标准参考帧并验证工具链：

```bash
make sender-conformance
```

## 编码后验收

编码前通过只说明绘制参数正确。还应从实际 H.264/WebRTC 输出解码一帧，再运行同一个校验命令。这样可以发现编码参数、后置缩放或转码造成的破坏。

验收顺序：

```text
编码前 PNG 通过
-> 本机编码/解码后的 PNG 通过
-> WHIP/WHEP 回环帧通过
-> 远端 Viewer 解码
```

如果编码前通过但编码后失败，检查码率、编码器色度转换和是否存在后置缩放。如果本机编码后通过但远端失败，检查服务端或中间代理是否转码。

## 启动日志

发送端启动时至少打印：

```text
ORTM protocol=ORTM-v0 profile=ortm-v0-fixed-720p
ORTM grid=32x32 x=24 y=24 cell=12 padding=12 box=408x408
ORTM background_alpha=0.15 cell_alpha=0.65 antialias=false
Final video caps: 1280x720
```

这几行用于确认远端没有加载错误 profile。

## 失败判断

| 结果 | 优先检查 |
| --- | --- |
| `resolution-mismatch` | 保存的帧不是最终 `1280x720` |
| `low-contrast` | alpha 太低、背景干扰或严重压缩 |
| `structure-mismatch` | marker 位置、cell、padding、缩放或码制不一致 |
| `crc-mismatch` | payload 位序、CRC 输入或图像损伤 |
| Viewer 时钟同步成功但 ORTM 解码失败 | 发送端 raster/码制问题，与 clock sync 无关 |

不要通过扩大 Viewer 搜索范围掩盖发送端布局错误。固定 profile 单帧验收通过，才表示发送端完成兼容。
