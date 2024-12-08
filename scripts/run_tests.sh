rm -rf reports
APP__LOGGING__SQL_LOG_LEVEL=DEBUG python -m pytest \
  --numprocesses=auto \
  --cov=slackhealthbot \
  --cov-report=xml \
  --cov-report=html \
  --junitxml="reports/junit.xml" \
  tests
mkdir -p reports
mv coverage.xml htmlcov reports/.
