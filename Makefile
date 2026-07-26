.PHONY: install test test-python docs-check web-install web-build web-e2e marketing-assets check test-all demo

install:
	./scripts/install.sh --source .

test: test-python

test-python:
	python3 -m unittest discover -s tests -v
	python3 -m compileall -q commons

docs-check:
	python3 scripts/check_docs.py

web-install:
	npm --prefix web ci

web-build:
	npm --prefix web run build

web-e2e:
	npm --prefix web run test:e2e

marketing-assets:
	node scripts/render_social_preview.mjs

check: test-python docs-check web-build

test-all: test-python docs-check web-build web-e2e

demo:
	@COMMONS_HOME="$$(mktemp -d)" python3 -m commons.cli --json test e2e --scenario all --agents codex,claude-code
