FROM debian:13-slim

LABEL org.opencontainers.image.title="ZT-SD-WAN Suricata sensor"
LABEL org.opencontainers.image.description="Passive SPAN sensor with ET Open rules"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates \
       iproute2 \
       jq \
       procps \
       suricata \
       suricata-update \
       tcpdump \
    && suricata-update --no-test \
    && sha256sum /var/lib/suricata/rules/suricata.rules \
       > /usr/share/suricata/et-open-rules.sha256 \
    && rm -rf /var/lib/apt/lists/*

CMD ["sleep", "infinity"]
