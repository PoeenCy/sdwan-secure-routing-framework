#!/bin/sh
set -eu

/usr/lib/frr/frrinit.sh start
exec sleep infinity
