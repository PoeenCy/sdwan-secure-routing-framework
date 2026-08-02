FROM debian:13-slim

LABEL org.opencontainers.image.title="ZT-SD-WAN Open vSwitch CPE"
LABEL org.opencontainers.image.description="Namespace-isolated OVS edge with GRE support"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates \
       iproute2 \
       iputils-ping \
       openvswitch-switch \
       procps \
       tcpdump \
       traceroute \
    && rm -rf /var/lib/apt/lists/*

COPY start-cpe.sh /usr/local/bin/start-cpe
RUN chmod 0755 /usr/local/bin/start-cpe

CMD ["/usr/local/bin/start-cpe"]
