FROM python:3.12.2-slim

WORKDIR /app

COPY requirements/prod.txt requirements.txt

RUN pip install -r requirements.txt
RUN opentelemetry-bootstrap -a install

COPY slackhealthbot slackhealthbot
COPY config/app-default.yaml config/app-default.yaml
COPY templates templates
COPY alembic.ini alembic.ini
COPY alembic alembic

CMD alembic upgrade head && opentelemetry-instrument --service_name slack-health-bot python -m slackhealthbot.main
