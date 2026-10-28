# Dashboard inspection uses only the standard Python library and static browser assets.
DASHBOARD_PORT ?= 8000
.PHONY: dashboard dashboard-export dashboard-test
dashboard-export:
	python3 scripts/export_dashboard.py
dashboard: dashboard-export
	python3 -m http.server $(DASHBOARD_PORT) --directory dashboard
dashboard-test:
	python3 -m unittest discover -s dashboard/tests -p 'test_*.py'
	node --test dashboard/tests/logic.test.mjs
	node --check dashboard/app.js

dashboard-publish:
	python3 scripts/publish_dashboard.py
dashboard-browser-test: dashboard-publish
	node dashboard/tests/browser.test.mjs
