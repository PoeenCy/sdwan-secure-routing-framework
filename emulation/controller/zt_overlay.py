from __future__ import annotations

import datetime as dt
import ipaddress
import json
import os
import struct
import time
from pathlib import Path
from typing import Any

import yaml
from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import (
    CONFIG_DISPATCHER,
    DEAD_DISPATCHER,
    MAIN_DISPATCHER,
    set_ev_cls,
)
from os_ken.lib import hub
from os_ken.lib.packet import arp, ethernet, ether_types, ipv4, packet
from os_ken.ofproto import ofproto_v1_3


PROBE_ETHERTYPE = 0x88B5
PROBE_MAGIC = b"ZTSP"
PROBE_VERSION = 1
PROBE_REQUEST = 0
PROBE_REPLY = 1
PROBE_FORMAT = "!4sBBHQQ"
PROBE_SIZE = struct.calcsize(PROBE_FORMAT)
ACCESS_OFPORT = 1


def _plain_ip(value: str) -> str:
    return str(ipaddress.ip_interface(value).ip)


class ZtOverlayController(app_manager.OSKenApp):
    """Default-deny L3 edge routing, fixed-path steering and GRE probes."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        config_path = Path(
            os.environ.get("ZT_OVERLAY_CONFIG", "/opt/zt/config/overlay.yaml")
        )
        with config_path.open("r", encoding="utf-8") as stream:
            self.config = yaml.safe_load(stream)

        self.sites: dict[str, dict[str, Any]] = dict(self.config["sites"])
        self.site_by_dpid = {
            int(site["dpid"], 16): site_id for site_id, site in self.sites.items()
        }
        self.site_by_host_ip = {
            _plain_ip(site["host_ip"]): site_id
            for site_id, site in self.sites.items()
        }
        self.tunnels = {
            tunnel["id"]: tunnel for tunnel in self.config["tunnels"]
        }
        self.policy_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
        for policy in self.config["policies"]:
            self.policy_by_pair[(policy["source"], policy["destination"])] = policy
            if policy.get("bidirectional", False):
                self.policy_by_pair[
                    (policy["destination"], policy["source"])
                ] = policy

        self.datapaths: dict[int, Any] = {}
        self.sequence = 0
        self.pending_probes: dict[tuple[int, int], dict[str, Any]] = {}
        self.probe_tokens = {
            index: tunnel_id
            for index, tunnel_id in enumerate(sorted(self.tunnels), start=1)
        }
        self.token_by_tunnel = {
            tunnel_id: token for token, tunnel_id in self.probe_tokens.items()
        }
        controller = self.config["controller"]
        self.probe_interval = float(controller["probe_interval_seconds"])
        self.probe_timeout = float(controller["probe_timeout_seconds"])
        self.telemetry_path = Path(controller["telemetry_path"])
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        self._probe_thread = hub.spawn(self._probe_loop)

    @staticmethod
    def _endpoint_for_site(tunnel: dict[str, Any], site_id: str) -> dict[str, Any]:
        for endpoint_name in ("left", "right"):
            endpoint = tunnel[endpoint_name]
            if endpoint["site"] == site_id:
                return endpoint
        raise KeyError(f"Site {site_id} is not an endpoint of {tunnel['id']}")

    @staticmethod
    def _other_endpoint(
        tunnel: dict[str, Any], site_id: str
    ) -> dict[str, Any]:
        if tunnel["left"]["site"] == site_id:
            return tunnel["right"]
        if tunnel["right"]["site"] == site_id:
            return tunnel["left"]
        raise KeyError(f"Site {site_id} is not an endpoint of {tunnel['id']}")

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change(self, event: Any) -> None:
        datapath = event.datapath
        if event.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
            self.logger.info("CPE connected dpid=%016x", datapath.id)
        elif event.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)
            self.logger.warning("CPE disconnected dpid=%016x", datapath.id)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features(self, event: Any) -> None:
        datapath = event.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        datapath.send_msg(
            parser.OFPFlowMod(
                datapath=datapath,
                command=ofproto.OFPFC_DELETE,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY,
                match=parser.OFPMatch(),
            )
        )
        self._add_flow(
            datapath,
            priority=0,
            match=parser.OFPMatch(),
            actions=[
                parser.OFPActionOutput(
                    ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER
                )
            ],
        )

    @staticmethod
    def _add_flow(
        datapath: Any,
        priority: int,
        match: Any,
        actions: list[Any],
        idle_timeout: int = 0,
    ) -> None:
        parser = datapath.ofproto_parser
        instructions = [
            parser.OFPInstructionActions(
                datapath.ofproto.OFPIT_APPLY_ACTIONS, actions
            )
        ]
        datapath.send_msg(
            parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=instructions,
                idle_timeout=idle_timeout,
            )
        )

    @staticmethod
    def _packet_out(
        datapath: Any, in_port: int, actions: list[Any], data: bytes
    ) -> None:
        parser = datapath.ofproto_parser
        datapath.send_msg(
            parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                in_port=in_port,
                actions=actions,
                data=data,
            )
        )

    def _reply_to_gateway_arp(
        self, datapath: Any, in_port: int, request: arp.arp, site_id: str
    ) -> None:
        site = self.sites[site_id]
        gateway_ip = _plain_ip(site["gateway_ip"])
        if request.dst_ip != gateway_ip:
            return
        reply = packet.Packet()
        reply.add_protocol(
            ethernet.ethernet(
                dst=request.src_mac,
                src=site["gateway_mac"],
                ethertype=ether_types.ETH_TYPE_ARP,
            )
        )
        reply.add_protocol(
            arp.arp(
                opcode=arp.ARP_REPLY,
                src_mac=site["gateway_mac"],
                src_ip=gateway_ip,
                dst_mac=request.src_mac,
                dst_ip=request.src_ip,
            )
        )
        reply.serialize()
        self._packet_out(
            datapath,
            datapath.ofproto.OFPP_CONTROLLER,
            [datapath.ofproto_parser.OFPActionOutput(in_port)],
            reply.data,
        )

    def _deny_ipv4(
        self, datapath: Any, in_port: int, ipv4_packet: ipv4.ipv4, reason: str
    ) -> None:
        parser = datapath.ofproto_parser
        self._add_flow(
            datapath,
            priority=200,
            match=parser.OFPMatch(
                in_port=in_port,
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_src=ipv4_packet.src,
                ipv4_dst=ipv4_packet.dst,
            ),
            actions=[],
            idle_timeout=15,
        )
        self.logger.warning(
            "default-deny src=%s dst=%s reason=%s",
            ipv4_packet.src,
            ipv4_packet.dst,
            reason,
        )

    def _route_ipv4(
        self,
        msg: Any,
        in_port: int,
        ipv4_packet: ipv4.ipv4,
        source_site_id: str,
    ) -> None:
        source_site = self.sites[source_site_id]
        if in_port != ACCESS_OFPORT:
            self._deny_ipv4(
                msg.datapath, in_port, ipv4_packet, "no pre-installed tunnel rule"
            )
            return
        if ipv4_packet.src != _plain_ip(source_site["host_ip"]):
            self._deny_ipv4(msg.datapath, in_port, ipv4_packet, "source spoofing")
            return
        destination_site_id = self.site_by_host_ip.get(ipv4_packet.dst)
        if destination_site_id is None:
            self._deny_ipv4(msg.datapath, in_port, ipv4_packet, "unknown destination")
            return
        policy = self.policy_by_pair.get((source_site_id, destination_site_id))
        if policy is None:
            self._deny_ipv4(msg.datapath, in_port, ipv4_packet, "policy missing")
            return

        tunnel = self.tunnels[policy["tunnel"]]
        source_endpoint = self._endpoint_for_site(tunnel, source_site_id)
        destination_endpoint = self._other_endpoint(tunnel, source_site_id)
        destination_site = self.sites[destination_site_id]
        destination_datapath = self.datapaths.get(
            int(destination_site["dpid"], 16)
        )
        if destination_datapath is None:
            self._deny_ipv4(
                msg.datapath, in_port, ipv4_packet, "destination CPE disconnected"
            )
            return

        destination_parser = destination_datapath.ofproto_parser
        destination_actions = [
            destination_parser.OFPActionSetField(
                eth_src=destination_site["gateway_mac"]
            ),
            destination_parser.OFPActionSetField(
                eth_dst=destination_site["host_mac"]
            ),
            destination_parser.OFPActionOutput(ACCESS_OFPORT),
        ]
        self._add_flow(
            destination_datapath,
            priority=300,
            match=destination_parser.OFPMatch(
                in_port=int(destination_endpoint["ofport"]),
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_src=ipv4_packet.src,
                ipv4_dst=ipv4_packet.dst,
            ),
            actions=destination_actions,
            idle_timeout=60,
        )

        source_parser = msg.datapath.ofproto_parser
        source_actions = [
            source_parser.OFPActionDecNwTtl(),
            source_parser.OFPActionSetField(eth_src=source_site["gateway_mac"]),
            source_parser.OFPActionSetField(
                eth_dst=destination_site["host_mac"]
            ),
            source_parser.OFPActionOutput(int(source_endpoint["ofport"])),
        ]
        self._add_flow(
            msg.datapath,
            priority=300,
            match=source_parser.OFPMatch(
                in_port=ACCESS_OFPORT,
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_src=ipv4_packet.src,
                ipv4_dst=ipv4_packet.dst,
            ),
            actions=source_actions,
            idle_timeout=60,
        )
        self._packet_out(msg.datapath, in_port, source_actions, msg.data)
        self.logger.info(
            "allow policy=%s src=%s dst=%s tunnel=%s path=%s",
            policy["id"],
            ipv4_packet.src,
            ipv4_packet.dst,
            tunnel["id"],
            tunnel["path"],
        )

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in(self, event: Any) -> None:
        msg = event.msg
        in_port = int(msg.match["in_port"])
        parsed = packet.Packet(msg.data)
        ethernet_packet = parsed.get_protocol(ethernet.ethernet)
        if ethernet_packet is None:
            return
        if ethernet_packet.ethertype == PROBE_ETHERTYPE:
            self._handle_probe(msg, in_port, ethernet_packet, msg.data)
            return

        site_id = self.site_by_dpid.get(msg.datapath.id)
        if site_id is None:
            self.logger.warning("Ignoring unknown dpid=%016x", msg.datapath.id)
            return
        arp_packet = parsed.get_protocol(arp.arp)
        if arp_packet is not None and arp_packet.opcode == arp.ARP_REQUEST:
            if in_port == ACCESS_OFPORT:
                self._reply_to_gateway_arp(
                    msg.datapath, in_port, arp_packet, site_id
                )
            return
        ipv4_packet = parsed.get_protocol(ipv4.ipv4)
        if ipv4_packet is not None:
            self._route_ipv4(msg, in_port, ipv4_packet, site_id)

    def _probe_payload(self, kind: int, token: int, seq: int, sent_ns: int) -> bytes:
        return struct.pack(
            PROBE_FORMAT,
            PROBE_MAGIC,
            PROBE_VERSION,
            kind,
            token,
            seq,
            sent_ns,
        )

    def _probe_frame(
        self, kind: int, token: int, seq: int, sent_ns: int
    ) -> bytes:
        frame = packet.Packet()
        frame.add_protocol(
            ethernet.ethernet(
                dst="02:ff:ff:ff:ff:fe",
                src=f"02:ff:00:00:{token >> 8:02x}:{token & 0xff:02x}",
                ethertype=PROBE_ETHERTYPE,
            )
        )
        frame.add_protocol(self._probe_payload(kind, token, seq, sent_ns))
        frame.serialize()
        return bytes(frame.data)

    def _handle_probe(
        self,
        msg: Any,
        in_port: int,
        ethernet_packet: ethernet.ethernet,
        raw_data: bytes,
    ) -> None:
        offset = 14
        if len(raw_data) < offset + PROBE_SIZE:
            return
        magic, version, kind, token, seq, sent_ns = struct.unpack(
            PROBE_FORMAT, raw_data[offset : offset + PROBE_SIZE]
        )
        tunnel_id = self.probe_tokens.get(token)
        if magic != PROBE_MAGIC or version != PROBE_VERSION or tunnel_id is None:
            return
        tunnel = self.tunnels[tunnel_id]
        if kind == PROBE_REQUEST:
            right = tunnel["right"]
            expected_dpid = int(self.sites[right["site"]]["dpid"], 16)
            if msg.datapath.id != expected_dpid or in_port != int(right["ofport"]):
                return
            reply = self._probe_frame(PROBE_REPLY, token, seq, sent_ns)
            parser = msg.datapath.ofproto_parser
            self._packet_out(
                msg.datapath,
                in_port,
                [parser.OFPActionOutput(msg.datapath.ofproto.OFPP_IN_PORT)],
                reply,
            )
            return
        if kind != PROBE_REPLY:
            return
        left = tunnel["left"]
        expected_dpid = int(self.sites[left["site"]]["dpid"], 16)
        if msg.datapath.id != expected_dpid or in_port != int(left["ofport"]):
            return
        pending = self.pending_probes.pop((token, seq), None)
        if pending is None:
            return
        rtt_ms = (time.monotonic_ns() - pending["started_ns"]) / 1_000_000
        self._write_probe_result(tunnel_id, seq, False, round(rtt_ms, 3))

    def _write_probe_result(
        self, tunnel_id: str, seq: int, lost: bool, rtt_ms: float | None
    ) -> None:
        tunnel = self.tunnels[tunnel_id]
        record = {
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "kind": "openflow_packet_out_gre_rtt",
            "tunnel": tunnel_id,
            "path": tunnel["path"],
            "sequence": seq,
            "lost": lost,
            "rtt_ms": rtt_ms,
        }
        with self.telemetry_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")

    def _expire_probes(self) -> None:
        now_ns = time.monotonic_ns()
        timeout_ns = int(self.probe_timeout * 1_000_000_000)
        expired = [
            key
            for key, value in self.pending_probes.items()
            if now_ns - value["started_ns"] >= timeout_ns
        ]
        for token, seq in expired:
            self.pending_probes.pop((token, seq), None)
            self._write_probe_result(self.probe_tokens[token], seq, True, None)

    def _probe_loop(self) -> None:
        while True:
            self._expire_probes()
            for tunnel_id in sorted(self.tunnels):
                tunnel = self.tunnels[tunnel_id]
                left = tunnel["left"]
                datapath = self.datapaths.get(
                    int(self.sites[left["site"]]["dpid"], 16)
                )
                if datapath is None:
                    continue
                self.sequence += 1
                token = self.token_by_tunnel[tunnel_id]
                sent_ns = time.monotonic_ns()
                self.pending_probes[(token, self.sequence)] = {
                    "started_ns": sent_ns
                }
                data = self._probe_frame(
                    PROBE_REQUEST, token, self.sequence, sent_ns
                )
                self._packet_out(
                    datapath,
                    datapath.ofproto.OFPP_CONTROLLER,
                    [
                        datapath.ofproto_parser.OFPActionOutput(
                            int(left["ofport"])
                        )
                    ],
                    data,
                )
            hub.sleep(self.probe_interval)
