FROM python:3.12.2-slim

WORKDIR /app

COPY requirements/prod.txt requirements.txt

RUN pip install -r requirements.txt

COPY slackhealthbot slackhealthbot
COPY config/app-default.yaml config/app-default.yaml
COPY templates templates
COPY alembic.ini alembic.ini
COPY alembic alembic

CMD alembic upgrade head && python -m slackhealthbot.main
