FROM python:3.11-slim

LABEL org.opencontainers.image.title="ZT-SD-WAN OS-Ken controller"
LABEL org.opencontainers.image.description="OpenFlow 1.3 controller pinned to OS-Ken 4.2.1"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       iproute2 \
       procps \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
      os-ken==4.2.1 \
      PyYAML==6.0.2

CMD ["sleep", "infinity"]
