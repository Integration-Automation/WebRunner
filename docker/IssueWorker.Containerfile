FROM python:3.11-slim

# Provision dependencies online once. Runtime checks use --pull=never and --network=none.
RUN apt-get update && apt-get install -y --no-install-recommends git chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*
COPY .github/requirements/ci.txt /opt/webrunner/ci.txt
RUN python -m pip install --no-cache-dir --require-hashes --only-binary :all: -r /opt/webrunner/ci.txt \
    && python -m pip install --no-cache-dir flake8==7.4.1 bandit==1.9.4 mypy==2.1.0 playwright==1.60.0 \
    && python -m playwright install --with-deps chromium \
    && chmod -R a+rX /root/.cache/ms-playwright \
    && mv /root/.cache/ms-playwright /opt/webrunner/browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/webrunner/browsers
ENV PYTHONDONTWRITEBYTECODE=1
USER 65532:65532
WORKDIR /work
