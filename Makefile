.PHONY: test test-python test-js vectors benchmark-smoke benchmark-matrix-smoke benchmark-codec-smoke benchmark-geometry-exploratory benchmark-resolution-exploratory benchmark-resolution-normalized-exploratory benchmark-matrix-report benchmark-codec-report benchmark-geometry-report benchmark-resolution-report benchmark-resolution-normalized-report

test: test-python test-js

test-python:
	PYTHONPATH=src/python python3 -m unittest discover -s tests -p 'test_*.py' -v

test-js:
	node --test tests/test_*.mjs

vectors:
	PYTHONPATH=src/python python3 tools/generate_vectors.py

benchmark-smoke:
	PYTHONPATH=src/python python3 tools/run_offline_benchmark.py \
		--scenario benchmarks/scenarios/h264-540p60-2500k.json \
		--output benchmark-results/h264-540p60-2500k \
		--overwrite

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
