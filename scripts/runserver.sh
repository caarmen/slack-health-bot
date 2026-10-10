#!/usr/bin/env bash

opentelemetry-instrument \
    --service_name slack-health-bot \
    python -m slackhealthbot.main

