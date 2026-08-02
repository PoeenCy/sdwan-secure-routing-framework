#!/bin/sh
set -eu

mkdir -p /var/run/openvswitch /var/log/openvswitch /var/lib/openvswitch
/usr/share/openvswitch/scripts/ovs-ctl \
    --system-id=random \
    --no-monitor \
    start

exec sleep infinity
