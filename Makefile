.PHONY: test test-python test-js vectors

test: test-python test-js

test-python:
	PYTHONPATH=src/python python3 -m unittest discover -s tests -p 'test_*.py' -v

test-js:
	node --test tests/test_*.mjs

vectors:
	PYTHONPATH=src/python python3 tools/generate_vectors.py
