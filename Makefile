.PHONY: install test test-python docs-check public-check release-source-check web-install web-build web-e2e video-install video-check marketing-assets check test-all demo

install:
	./scripts/install.sh --source .

test: test-python

test-python:
	python3 -m unittest discover -s tests -v
	python3 -m compileall -q commons

docs-check:
	python3 scripts/check_docs.py

public-check:
	python3 scripts/check_public_tree.py

release-source-check:
	python3 scripts/check_release_artifacts.py

web-install:
	npm --prefix web ci

web-build:
	npm --prefix web run build

web-e2e:
	npm --prefix web run test:e2e

video-install:
	npm --prefix video ci

video-check:
	npm --prefix video run check

marketing-assets:
	node scripts/render_social_preview.mjs

check: test-python docs-check public-check release-source-check web-build video-check

test-all: test-python docs-check public-check release-source-check web-build web-e2e video-check

demo:
	@COMMONS_HOME="$$(mktemp -d)" python3 -m commons.cli --json test e2e --scenario all --agents codex,claude-code
