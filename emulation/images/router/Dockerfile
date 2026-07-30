FROM debian:13-slim AS ditg-builder

ARG DITG_URL=https://traffic.comics.unina.it/software/ITG/codice/D-ITG-2.8.1-r1023-src.zip
ARG DITG_SHA256=e3974b167a684110cacb0436193d5dabdfc90d2c8e1bb18838e20c75bd406ebf

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates \
       curl \
       g++ \
       make \
       patch \
       unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY d-itg-gcc14.patch /build/d-itg-gcc14.patch

RUN curl -fsSL "${DITG_URL}" -o d-itg.zip \
    && echo "${DITG_SHA256}  d-itg.zip" | sha256sum -c - \
    && unzip -q d-itg.zip \
    && patch -p0 < d-itg-gcc14.patch \
    && make -C D-ITG-2.8.1-r1023/src -j2 \
       BASEDIR=/build/D-ITG-2.8.1-r1023/src \
       CXXOPT="-O2 -std=gnu++11 -DBURSTY -DMULTIPORT"

FROM debian:13-slim

LABEL org.opencontainers.image.title="ZT-SD-WAN routed underlay router"
LABEL org.opencontainers.image.description="FRR router with pinned D-ITG 2.8.1-r1023"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       frr \
       frr-pythontools \
       iproute2 \
       iputils-ping \
       iperf3 \
       libstdc++6 \
       procps \
       tcpdump \
       traceroute \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ditg-builder \
    /build/D-ITG-2.8.1-r1023/bin/ITGSend \
    /build/D-ITG-2.8.1-r1023/bin/ITGRecv \
    /build/D-ITG-2.8.1-r1023/bin/ITGDec \
    /usr/local/bin/
COPY start-router.sh /usr/local/bin/start-router
RUN chmod 0755 /usr/local/bin/start-router \
    && sed -i 's/^zebra=no/zebra=yes/' /etc/frr/daemons \
    && sed -i 's/^ospfd=no/ospfd=yes/' /etc/frr/daemons

CMD ["/usr/local/bin/start-router"]
