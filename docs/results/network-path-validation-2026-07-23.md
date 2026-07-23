# Direct network impairment path validation

Date: 2026-07-23

## Purpose

This short calibration verifies that `fish_front` publisher media packets
traverse the Docker `eth0` qdisc controlled by the ORTM network benchmark
adapter. It is an infrastructure check, not a robustness result.

## Method

- path: GStreamer publisher to local MediaMTX to Direct WebRTC viewer;
- stream: `fish_front`;
- publisher profile: approximately 960x540, 60 fps, 2.5 Mbps;
- conditions: clear, 50 ms publisher-egress delay, 0.5% random loss;
- one randomized run per condition;
- 3-second warm-up and 8-second observation;
- 2-second monitor sampling;
- four clock-valid samples per condition.

## Qdisc evidence

| Condition | Bytes through qdisc | Packets through qdisc | Dropped | End backlog |
| --- | ---: | ---: | ---: | ---: |
| clear | 0 | 0 | 0 | 0 |
| delay50 | 3,048,731 | 2,922 | 0 | 18,093 bytes / 19 packets |
| loss0.5 | 3,054,928 | 2,934 | 17 | 0 |

The observed loss was approximately 0.58% when dropped packets are included in
the attempted-packet denominator. The delay condition retained 19 packets in
the configured 50 ms queue at the final inspection.

## Viewer observations

| Condition | ORTM median | ORTM p95 | Upstream median | Minimum receive FPS | Freeze delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| clear | 123.0 ms | 123.0 ms | 100.0 ms | 58.9 | 0 |
| delay50 | 192.5 ms | 208.3 ms | 169.0 ms | 59.0 | 0 |
| loss0.5 | 103.0 ms | 108.6 ms | 80.0 ms | 39.0 | 10 |

The 50 ms qdisc delay increased median approximate G2G by 69.5 ms and median
upstream latency by 69.0 ms in this calibration. This confirms that the
impairment point is observable by ORTM. The loss condition produced ten freeze
events despite its lower short-window latency median; latency medians from this
single eight-second run must not be interpreted as a loss-performance result.

## Conclusion

The adapter targets the intended publisher media path, and end-of-condition
`tc -s qdisc` output provides packet-level evidence for every impaired run.
Longer randomized repetitions are still required for robustness claims.
