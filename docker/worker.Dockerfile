FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    wget \
    gnupg \
    xvfb \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    ca-certificates \
    && wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python3 -c "\
import re, pathlib; \
f = pathlib.Path('/usr/local/lib/python3.11/site-packages/zendriver/cdp/network.py'); \
t = f.read_text(); \
t = t.replace(\
'private_network_request_policy=PrivateNetworkRequestPolicy.from_json(\n                json[\"privateNetworkRequestPolicy\"]\n            ),', \
'private_network_request_policy=PrivateNetworkRequestPolicy.from_json(json[\"privateNetworkRequestPolicy\"]) if \"privateNetworkRequestPolicy\" in json else PrivateNetworkRequestPolicy.ALLOW,'); \
f.write_text(t); \
print('patched ok') \
"

COPY . .

ENV PYTHONUNBUFFERED=1
