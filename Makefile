.PHONY: test test-python test-js vectors sender-conformance benchmark-smoke benchmark-minimal-720p benchmark-finder-layout-formal benchmark-finder-layout-report benchmark-matrix-smoke benchmark-codec-smoke benchmark-geometry-exploratory benchmark-resolution-exploratory benchmark-resolution-normalized-exploratory benchmark-network-dry-run benchmark-matrix-report benchmark-codec-report benchmark-geometry-report benchmark-resolution-report benchmark-resolution-normalized-report

test: test-python test-js

test-python:
	PYTHONPATH=src/python python3 -m unittest discover -s tests -p 'test_*.py' -v

test-js:
	node --test tests/test_*.mjs

vectors:
	PYTHONPATH=src/python python3 tools/generate_vectors.py

sender-conformance:
	PYTHONPATH=src/python python3 tools/generate_reference_frame.py
	PYTHONPATH=src/python python3 tools/validate_frame.py \
		--input fixtures/ortm-v0-fixed-720p.png

benchmark-smoke:
	PYTHONPATH=src/python python3 tools/run_offline_benchmark.py \
		--scenario benchmarks/scenarios/h264-540p60-2500k.json \
		--output benchmark-results/h264-540p60-2500k \
		--overwrite

benchmark-minimal-720p:
	PYTHONPATH=src/python python3 tools/run_offline_benchmark.py \
		--scenario benchmarks/scenarios/h264-720p60-2500k-minimal.json \
		--output benchmark-results/h264-720p60-2500k-minimal \
		--overwrite

benchmark-finder-layout-formal:
	PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
		--matrix benchmarks/matrices/finder-layout-formal.json \
		--output benchmark-results/finder-layout-formal \
		--overwrite

benchmark-finder-layout-report:
	python3 tools/render_matrix_report.py \
		--summary benchmark-results/finder-layout-formal/summary.json \
		--output docs/results/finder-layout-formal-2026-08-04.md \
		--artifact-path benchmark-results/finder-layout-formal

benchmark-matrix-smoke:
	PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
		--matrix benchmarks/matrices/h264-core-smoke.json \
		--output benchmark-results/h264-core-smoke \
		--overwrite

benchmark-codec-smoke:
	PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
		--matrix benchmarks/matrices/codec-core-smoke.json \
		--output benchmark-results/codec-core-smoke \
		--overwrite

benchmark-geometry-exploratory:
	PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
		--matrix benchmarks/matrices/geometry-cell-exploratory.json \
		--output benchmark-results/geometry-cell-exploratory \
		--overwrite

benchmark-resolution-exploratory:
	PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
		--matrix benchmarks/matrices/resolution-fixed-cell6-exploratory.json \
		--output benchmark-results/resolution-fixed-cell6-exploratory \
		--overwrite

benchmark-resolution-normalized-exploratory:
	PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
		--matrix benchmarks/matrices/resolution-normalized-exploratory.json \
		--output benchmark-results/resolution-normalized-exploratory \
		--overwrite

benchmark-network-dry-run:
	python3 tools/run_network_matrix.py \
		--matrix benchmarks/network/tunnel-direct-single-factor-smoke.json \
		--output benchmark-results/network-dry-run \
		--dry-run

benchmark-matrix-report:
	python3 tools/render_matrix_report.py \
		--summary benchmark-results/h264-core-formal/summary.json \
		--output docs/results/h264-core-formal-2026-07-22.md \
		--artifact-path benchmark-results/h264-core-formal

benchmark-codec-report:
	python3 tools/render_matrix_report.py \
		--summary benchmark-results/codec-core-formal/summary.json \
		--output docs/results/codec-core-formal-2026-07-23.md \
		--artifact-path benchmark-results/codec-core-formal

benchmark-geometry-report:
	python3 tools/render_matrix_report.py \
		--summary benchmark-results/geometry-cell-formal/summary.json \
		--output docs/results/geometry-cell-formal-2026-07-23.md \
		--artifact-path benchmark-results/geometry-cell-formal

benchmark-resolution-report:
	python3 tools/render_matrix_report.py \
		--summary benchmark-results/resolution-fixed-cell6-formal/summary.json \
		--output docs/results/resolution-fixed-cell6-formal-2026-07-23.md \
		--artifact-path benchmark-results/resolution-fixed-cell6-formal

benchmark-resolution-normalized-report:
	python3 tools/render_matrix_report.py \
		--summary benchmark-results/resolution-normalized-formal/summary.json \
		--output docs/results/resolution-normalized-formal-2026-07-23.md \
		--artifact-path benchmark-results/resolution-normalized-formal
