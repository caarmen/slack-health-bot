#!/usr/bin/env bash
rm -rf reports
python -m pytest \
  --numprocesses=auto \
  --cov=slackhealthbot \
  --cov-report=xml \
  --cov-report=html \
  --junitxml="reports/junit.xml" \
  tests \
  $*
mkdir -p reports
mv coverage.xml htmlcov reports/.
