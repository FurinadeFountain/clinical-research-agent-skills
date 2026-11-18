.PHONY: check clean
PYTHON ?= python3

check:
	$(PYTHON) -B scripts/lint_agent_configs.py
	$(PYTHON) -B -m unittest discover -s scripts -p 'test_*.py'
	$(PYTHON) -B -m unittest discover -s skills/scientific-drafting/scripts -p 'test_*.py'
	$(PYTHON) -B -m unittest discover -s skills/scientific-visualization/scripts -p 'test_*.py'
	$(PYTHON) -B -m unittest discover -s skills/zotero-verified-bibliography/scripts -p 'test_*.py'
	$(PYTHON) -B -m unittest discover -s skills/ncbi-pmc/scripts -p 'test_*.py'
	$(PYTHON) -B -m unittest discover -s skills/ncbi-entrez/scripts -p 'test_*.py'
	$(PYTHON) -B -m unittest discover -s examples/experimental-unit -p 'test_*.py'
	$(PYTHON) -B -m unittest discover -s examples/manuscript-review-triage -p 'test_*.py'

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
