FROM debian:13-slim

LABEL org.opencontainers.image.title="ZT-SD-WAN enterprise endpoint"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates \
       curl \
       iperf3 \
       iproute2 \
       iputils-ping \
       netcat-openbsd \
       procps \
       python3 \
       tcpdump \
       traceroute \
    && rm -rf /var/lib/apt/lists/*

CMD ["sleep", "infinity"]
