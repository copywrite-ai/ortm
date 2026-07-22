.PHONY: test test-python test-js vectors benchmark-smoke

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
