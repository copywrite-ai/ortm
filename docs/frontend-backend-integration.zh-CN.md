# ORTM 前后端接入指南

本文说明如何把 ORTM 接入一条正式的视频链路，包括：

- GStreamer 发送端在编码前写入 ORTM；
- Web 前端从解码后的视频帧恢复时间戳；
- BFF 提供媒体地址、访问控制和遥测接收；
- Prometheus/Grafana 汇总 ORTM 与传输指标。

ORTM 与媒体协议无关。本文使用 WHIP/WHEP 和 WebRTC 作为示例，也可以替换为 RTSP、SRT 或其他能够保留视频像素的链路。

## 1. 测量边界

推荐链路：

```text
摄像头或测试源
→ ORTM overlay
→ 视频编码
→ 媒体传输
→ 视频解码
→ Web/Native 播放器获得视频帧
→ ORTM decode
```

ORTM 近似测量：

```text
编码前写入时间戳
→ 编码
→ 传输
→ 解码
→ 播放器获得可观察视频帧
```

ORTM 本身不覆盖摄像头曝光之前的时间，也不能证明帧已经完成物理屏幕 scan-out。严格 glass-to-glass 结论需要高速摄像机、光电传感器或其他外部光学基准校准。

发送端和观看端使用不同机器时，必须先完成可靠的墙钟同步。时间不同步不会必然导致 CRC 失败，但会直接污染延迟结果。

## 2. 组件职责

### ORTM 核心库

ORTM 核心库负责：

- v0 marker 编码和 CRC；
- 固定 ROI 栅格解码；
- 时间戳低 32 位回绕处理；
- 解码结构、对比度和时间范围诊断。

ORTM 核心库不负责：

- 摄像头采集；
- WHIP/WHEP 信令；
- WebRTC ICE/TURN；
- 用户鉴权；
- 指标存储和可视化。

### 发送端

发送端负责在每一帧编码前绘制 marker，并保证：

- ORTM 位于固定位置；
- overlay 后再进入编码器；
- `frame_seq` 每帧递增；
- `timestamp_ms` 来自同步后的墙钟；
- 编码缩放不会破坏 marker 边界。

### Web 前端

前端负责：

- 播放发送端的视频；
- 从视频帧固定 ROI 解码 ORTM；
- 把成功样本、失败原因和 WebRTC 指标关联起来；
- 展示近似 G2G、freeze 和解码质量。

前端不需要为了观看视频而访问观看端摄像头。

### BFF

BFF 是可选的应用层组件，通常负责：

- 用户和设备鉴权；
- 返回媒体播放地址；
- 代理 WHEP 等媒体信令接口；
- 接收浏览器遥测；
- 隐藏内部 Media Server 地址和管理凭据。

ORTM 解码完全可以在浏览器本地完成，不要求把视频帧上传给 BFF。

### 时钟校准接口

ORTM v0 在画面中携带发送端墙钟时间，但码制本身不负责同步两端系统时钟。
仓库提供可选的四时间戳 HTTP 参考实现：

```text
src/js/clock-sync.js
src/node/clock-sync.js
examples/clock-sync-server.mjs
```

每个视频源应作为一个完整配置交给前端：

```js
{
  whepUrl: 'https://publisher-a.example/fish_front/whep',
  clockSyncUrl: 'https://publisher-a.example/api/clock-sync',
  clockId: 'publisher-a',
}
```

`clockSyncUrl` 必须对应真正写入 ORTM 时间戳的 Publisher 时钟，不能默认使用
播放页面的同源地址。四路来自不同 Publisher 时，应分别维护四份校准结果。
前端应校验接口返回的 `clockId`，不匹配时停止输出校正后的近似 G2G。

如果根据 WHEP origin 自动推导，必须保留端口：

```text
https://publisher.example:8889/fish_front/whep
-> https://publisher.example:8889/api/clock-sync
```

因此 `:8889` 的反向代理必须把 `/api/clock-sync` 转发到时钟服务，而不是
MediaMTX。若时钟服务没有挂在同一个公开 origin，必须显式提供
`clockSyncUrl`。HTTPS 页面不能直接访问 `http://publisher:9011`，应先通过
HTTPS 反向代理。

协议字段必须是 Unix 毫秒数值：

```text
serverReceiveUnixMs
serverSendUnixMs
```

已有服务若使用 `server_receive_ms`、`server_transmit_ms` 等字段，应通过
`payloadAdapter` 显式映射。`structure-mismatch` 属于 Marker/ROI 问题，
与时钟同步是否成功无关。

协议和部署方式见 [`docs/clock-sync.md`](clock-sync.md)。

## 3. GStreamer 发送端接入

仓库提供 `cairooverlay` 参考 adapter：

```text
integrations/gstreamer/ortm_overlay.py
```

安装并运行示例：

```bash
python3 -m pip install -e .
PYTHONPATH=integrations/gstreamer python3 examples/gstreamer_testsrc.py
```

正式 pipeline 的顺序必须是：

```text
source
→ raw video conversion/caps
→ cairooverlay name=ortm_overlay
→ encoder
→ parser/payloader
→ media sink
```

Python 接入示例：

```python
from ortm_overlay import OrtmCairoOverlay, attach_to_pipeline

pipeline = Gst.parse_launch(
    "videotestsrc is-live=true "
    "! video/x-raw,width=960,height=540,framerate=60/1 "
    "! cairooverlay name=ortm_overlay "
    "! videoconvert "
    "! x264enc tune=zerolatency speed-preset=ultrafast "
    "! ..."
)

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

默认的低影响绘制参数是当前验证基线。降低 alpha、缩小 cell 或在编码后叠加，都可能降低解码成功率。

使用 `whipclientsink` 时，WHIP endpoint 和 request pad 的配置属于 GStreamer/WebRTC transport，不属于 ORTM adapter。应以所安装插件版本的文档为准。

## 4. Web 前端安装

从 Git 仓库安装 JavaScript 参考实现：

```bash
npm install git+https://github.com/copywrite-ai/ortm.git
```

导入固定 ROI decoder：

```js
import {
  DEFAULT_RASTER_PROFILE,
  buildReadRoi,
  decodeRgbaImage,
} from 'open-raster-timing-marker/raster';
```

如果产品不使用 npm，也可以把以下两个 ES module vendoring 到自己的静态资源中：

```text
src/js/ortm.js
src/js/raster.js
```

两个文件需要保持同一版本，不要只更新其中一个。

## 5. Web 固定 ROI 解码

下面的代码只读取 marker 周围的小区域，不对完整视频帧执行图像搜索：

```js
const profile = {
  ...DEFAULT_RASTER_PROFILE,
  scales: [1.0, 0.95, 1.05, 0.9, 1.1],
  offsets: [0, -4, 4],
};
const roi = buildReadRoi(profile);
const canvas = document.createElement('canvas');
canvas.width = roi.width;
canvas.height = roi.height;
const context = canvas.getContext('2d', { willReadFrequently: true });

function decodeCurrentFrame(video) {
  if (!video.videoWidth || !video.videoHeight) return null;

  context.drawImage(
    video,
    roi.x,
    roi.y,
    roi.width,
    roi.height,
    0,
    0,
    roi.width,
    roi.height,
  );
  const imageData = context.getImageData(0, 0, roi.width, roi.height);
  return decodeRgbaImage(
    imageData,
    video.videoWidth,
    video.videoHeight,
    Date.now(),
    { profile, roiX: roi.x, roiY: roi.y },
  );
}
```

推荐使用 `requestVideoFrameCallback` 对齐新视频帧，并限制图像读取频率：

```js
let lastDecodeAt = 0;

function onVideoFrame(now) {
  if (now - lastDecodeAt >= 200) {
    lastDecodeAt = now;
    const result = decodeCurrentFrame(video);
    consumeOrtmResult(result);
  }
  video.requestVideoFrameCallback(onVideoFrame);
}

video.requestVideoFrameCallback(onVideoFrame);
```

200 ms 解码一次不会给成功样本额外增加 200 ms 延迟。它只降低采样密度：每次仍然用当前视频帧内时间戳与当前墙钟相减。

## 6. 解码结果处理

成功结果示例：

```json
{
  "ok": true,
  "version": 0,
  "frame_seq": 1234,
  "timestamp_ms": 305419896,
  "latency_ms": 82,
  "raw_age_ms": 82,
  "finder_errors": 0,
  "timing_errors": 0,
  "contrast": 164.2
}
```

应用层应遵循以下规则：

- 只有 `ok=true` 的样本进入正常延迟分位数和曲线；
- `frame_seq` 长时间不变表示画面或解码样本可能冻结；
- `crc-mismatch` 表示 payload 不可信；
- `structure-mismatch` 表示 finder/timing 不匹配；
- `low-contrast` 表示 marker 与背景区分不足；
- `latency-out-of-range` 通常表示时钟偏差或异常陈旧帧；
- 时间越界时记录 `raw_age_ms`，但不要把它当正常 G2G 样本。

前端应把 ORTM 解码失败与视频 freeze 分开。视频帧不更新时，`requestVideoFrameCallback` 可能不再触发，因此还需要独立的 wall-clock timer 计算样本年龄。

## 7. 媒体播放与 WHEP

ORTM 不要求使用 WHEP，但 WebRTC/WHEP 是当前低延迟 Web 产品的推荐组合之一：

```text
GStreamer Publisher
→ WHIP
→ Media Server
→ WHEP
→ HTMLVideoElement
→ ORTM decoder
```

前端播放器需要：

1. 创建 `recvonly` video transceiver；
2. 生成 offer 并完成 ICE gathering；
3. `POST application/sdp` 到 WHEP endpoint；
4. 设置返回的 answer SDP；
5. 保存 `Location` session URL；
6. 停止时向 session URL 发送 `DELETE` 并关闭 PeerConnection。

业务公开地址建议与页面同源，且 endpoint 末尾不带 `/`：

```text
https://video.example.com/fish_front/whep
```

完整的 WHIP/WHEP、TURN、MediaMTX 和 Grafana 工程示例位于：

```text
https://github.com/copywrite-ai/webrtc-coturn/tree/codex/whep-evolution
```

该仓库是集成实验室，不是 ORTM 规范的一部分。

## 8. BFF 接口建议

### 播放配置

```http
GET /api/video/streams/fish_front
```

```json
{
  "stream": "fish_front",
  "whepUrl": "/fish_front/whep",
  "transportMode": "direct",
  "ortm": {
    "enabled": true,
    "version": 0,
    "profile": "fixed-roi-default"
  }
}
```

BFF 不应返回 TURN shared secret、Media Server 管理密码或其他长期凭据。强制 relay 时，应返回有过期时间的临时 TURN username/credential。

### WHEP 代理

BFF 或 Ingress 代理 WHEP 时必须保留：

| 项目 | 要求 |
| --- | --- |
| 方法 | `POST`、`DELETE`；启用 trickle ICE 时还要支持 `PATCH` |
| 请求体 | SDP 或 ICE fragment，不能按 JSON 解析 |
| 状态码 | 保留上游 `201`、`204`、`4xx` 和 `5xx` |
| `Location` | 重写为浏览器可访问的同源 session URL |
| 鉴权 | 校验用户是否有权读取指定 stream |

推荐映射：

```text
公开：https://video.example.com/fish_front/whep
内部：http://media-server:8889/fish_front/whep
```

### 遥测接收

推荐使用结构化 JSON，而不是让后端解析 UI 文本：

```http
POST /api/video/telemetry
Content-Type: application/json
```

```json
{
  "stream": "fish_front",
  "sessionId": "viewer-session-id",
  "observedAt": "2026-07-22T09:00:00.000Z",
  "ortm": {
    "ok": true,
    "latencyMs": 82,
    "rawAgeMs": 82,
    "frameSeq": 1234,
    "decodeSuccessPercent": 100,
    "contrast": 164.2
  },
  "webrtc": {
    "fps": 60,
    "bitrateKbps": 2510,
    "jitterBufferMs": 24,
    "packetsLost": 0,
    "freezeCount": 0
  }
}
```

BFF 应实施身份校验、body 大小限制、频率限制、字段白名单和数值范围校验。浏览器遥测适合观测，不应直接用于权限、安全或计费决策。

## 9. Prometheus 指标建议

推荐至少暴露：

```text
video_ortm_latency_ms
video_ortm_raw_age_ms
video_ortm_decode_success_percent
video_ortm_crc_failures_total
video_ortm_structure_failures_total
video_ortm_low_contrast_failures_total
video_ortm_latency_range_failures_total
video_frame_stall_ms
video_receive_fps
video_receive_bitrate_kbps
video_jitter_buffer_ms
video_packets_lost_total
```

ORTM 指标应与编码器、传输和播放器指标放在同一时间轴上。单独观察 G2G 数值无法判断异常来自发送端、网络、解码器还是显示调度。

建议标签保持低基数：

```text
stream="fish_front"
transport="direct|relay"
client="web|native"
```

不要把用户 ID、session ID 或完整 URL 直接作为 Prometheus label。

## 10. Direct 与 relay

ORTM payload 和 decoder 在 direct、DERP 或 TURN relay 下完全相同。切换传输路径时，不应修改 marker 版本和流名称，这样才能对比同一业务流。

建议顺序：

1. 先在 direct、本机或稳定局域网建立基线；
2. 再测试跨网络 direct/DERP；
3. 最后强制 TURN relay；
4. 对比 median、p95、p99、freeze 和解码成功率。

如果 direct 尚不稳定，先不要把 relay 引入同一轮根因分析。

## 11. 安全与隐私

- ORTM 写入的是墙钟低 32 位和递增序号，不应承载用户身份或业务数据；
- 不要把 TURN secret、媒体服务管理凭据放到浏览器；
- WHEP endpoint 必须有业务鉴权或受控网络边界；
- 遥测 endpoint 必须限流；
- `/metrics` 不应直接暴露到公网；
- 视频帧通常不需要上传到遥测后端，前端只上报解码结果和统计值。

## 12. 接入验收清单

发送端：

- overlay 位于编码器之前；
- 实际 FPS 和码率符合目标；
- marker 在目标分辨率和复杂背景下稳定可解；
- `frame_seq` 连续递增；
- 时钟同步状态可观测。

前端：

- 只读取固定 ROI；
- ORTM 解码不会阻塞主线程和视频播放；
- 失败样本不会污染正常延迟统计；
- 能区分帧冻结、解码失败和时钟越界；
- 停止和重连会清理旧媒体 session。

BFF 与监控：

- 媒体地址经过鉴权；
- WHEP `Location` 重写正确；
- 遥测有认证、限流和校验；
- Prometheus 能同时观察 ORTM、发送端、传输和播放器指标；
- Dashboard 展示 median、p95、p99、freeze 和解码质量。
