import uuid
from src.models.flow import Flow
from src.models.events import CUpdated, TrustUpdated
from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.action_mask import ActionMask
from src.routing.feasible_paths import FeasiblePaths
from src.routing.heuristic_agent import HeuristicAgent

class SDWANController:
    def __init__(self, overlay_manager: OverlayManager, pdp: PDP, 
                 zone_matrix: ZoneMatrix, bridge: CGBridge, agent: HeuristicAgent):
        self.overlay_manager = overlay_manager
        self.pdp = pdp
        self.zone_matrix = zone_matrix
        self.bridge = bridge
        self.agent = agent
        
        self.active_flows = {}  # flow_id -> Flow object
        
        # Register for events from overlay manager
        self.overlay_manager.register_listener(self.handle_event)
        
        # Initial Attack Graph generation
        self.bridge.regenerate_g(self.overlay_manager.get_c())

    def handle_event(self, event):
        """Dispatches event to appropriate handler."""
        if isinstance(event, CUpdated):
            self.on_event_c_updated(event)
        elif isinstance(event, TrustUpdated):
            self.on_event_trust_updated(event)

    def on_flow_request(self, s: str, d: str, service_type: str) -> Flow:
        """
        Processes a new flow connection request (s -> d) through the security pipeline.
        """
        s_str, d_str = str(s), str(d)
        C = self.overlay_manager.get_c()
        zone_s = C.get_zone(s_str)
        zone_d = C.get_zone(d_str)
        
        flow_id = str(uuid.uuid4())[:8]
        flow = Flow(flow_id, s_str, d_str, service_type)

        # 1. Micro-segmentation Layer Check
        if not self.zone_matrix.is_allowed(zone_s, zone_d):
            flow.status = "DENY_ZONE_BLOCKED"
            print(f"[Controller] Flow request {s_str}->{d_str} denied: Micro-segmentation block ({zone_s} to {zone_d})")
            return flow

        # 2. PDP Trust Check at Source Node
        theta_path = self.pdp.get_theta_path(zone_s, zone_d, C)
        if not self.pdp.evaluate_node(s_str, zone_s, theta_path, C):
            flow.status = "DENY_TRUST_BLOCKED"
            print(f"[Controller] Flow request {s_str}->{d_str} denied: Source trust score below threshold")
            return flow

        # 3. Action Mask & Path Selection
        struct_mask = self.bridge.get_struct_mask()
        node_masks = ActionMask.build_node_masks(C, self.pdp, s_str, d_str, struct_mask)
        
        # Get feasible edges E_f
        E_f = ActionMask.get_feasible_edges(C, node_masks, self.zone_matrix)
        
        # Find paths P_f
        P_f = FeasiblePaths.find_paths(s_str, d_str, E_f)
        
        if not P_f:
            flow.status = "DENY_NO_PATH"
            print(f"[Controller] Flow request {s_str}->{d_str} denied: No ZT-SR feasible path found")
            return flow

        # 4. Route Selection via Heuristic Agent
        path, reward = self.agent.select_path(s_str, d_str, P_f, C, self.bridge)
        if path:
            flow.path = path
            flow.status = "ACTIVE"
            self.active_flows[flow.flow_id] = flow
            print(f"[Controller] Flow {flow.flow_id} installed: Path={path}, Reward={reward:.2f}")
        else:
            flow.status = "DENY_NO_PATH"
            print(f"[Controller] Flow request {s_str}->{d_str} denied: Heuristic routing failed to select path")
            
        return flow

    def trigger_trust_update(self, node_id: str, component: str, new_value: float):
        """Simulates an external threat intelligence event updating trust score."""
        node_str = str(node_id)
        C = self.overlay_manager.get_c()
        zone = C.get_zone(node_str)
        
        # Get old values
        if component == 'I':
            old_val = self.pdp.identity.get_score(node_str)
            self.pdp.identity.set_score(node_str, new_value)
        elif component == 'C':
            old_val = self.pdp.context.get_score(node_str, zone)
            # In ContextProvider, we set patch_factor
            self.pdp.context.set_patch_factor(node_str, new_value)
        elif component == 'B':
            old_val = self.pdp.behavior.get_score(node_str)
            self.pdp.behavior.set_score(node_str, new_value)
        else:
            return
            
        event = TrustUpdated(node_str, component, old_val, new_value)
        self.handle_event(event)

    def on_event_c_updated(self, event: CUpdated):
        """
        Handles CUpdated events:
        - Regenerates attack graph G
        - Recalculates Z-score thresholds
        - Re-evaluates active flows for mandatory re-routing (structural or QoS violation)
        """
        C = self.overlay_manager.get_c()
        # Regenerate attack graph
        self.bridge.regenerate_g(C)
        print(f"[Controller] Event handling: C updated. G regenerated. New thresholds: theta_BN={self.bridge.theta_bn:.4f}, theta_MOD={self.bridge.theta_mod:.4f}")

        # Check all active flows for mandatory re-route
        affected_flow_ids = []
        for flow_id, flow in self.active_flows.items():
            if flow.status != "ACTIVE" and flow.status != "REROUTED":
                continue
                
            path = flow.path
            # Check 1: Does path contain cut edges (bandwidth = 0)?
            has_cut = False
            for i in range(len(path) - 1):
                u, v = path[i], path[i+1]
                if C[u][v].get('bandwidth_mbps', 0.0) <= 0.0:
                    has_cut = True
                    break
            
            # Check 2: SLA Violation (Delay check)
            total_delay = 0.0
            for i in range(len(path) - 1):
                u, v = path[i], path[i+1]
                total_delay += C[u][v].get('delay_ms', 0.0)
            
            from src.routing.qos_catalog import services_limit
            # VoIP delay SLA is 150ms, Generic is 500ms
            max_delay = 150.0 if flow.service_type == "VoIP" else 500.0
            sla_violated = (total_delay > max_delay)

            # Check 3: Structural Violation (Nodes in path become structural outliers)
            struct_mask = self.bridge.get_struct_mask()
            struct_violated = False
            for node in path:
                node_str = str(node)
                zone_node = C.get_zone(node_str)
                # Exempt Core, source, and destination from structural blocking checks
                if str(zone_node).lower() != 'core' and node_str != str(flow.s) and node_str != str(flow.d):
                    if not struct_mask.get(node_str, True):
                        struct_violated = True
                        break

            if has_cut or sla_violated or struct_violated:
                print(f"[Controller] Flow {flow_id} requires mandatory re-route: cut={has_cut}, SLA violated={sla_violated}, struct violated={struct_violated}")
                affected_flow_ids.append(flow_id)

        # Trigger re-routing for affected flows
        for flow_id in affected_flow_ids:
            self.re_route_flow(flow_id)

    def on_event_trust_updated(self, event: TrustUpdated):
        """
        Handles TrustUpdated events:
        - Checks if any active flow uses the compromised node.
        - Verifies if the node's trust score drops below the path threshold.
        - Triggers mandatory re-routing or termination.
        """
        compromised_node = event.node
        C = self.overlay_manager.get_c()
        
        affected_flow_ids = []
        for flow_id, flow in self.active_flows.items():
            if flow.status != "ACTIVE" and flow.status != "REROUTED":
                continue
                
            if compromised_node in flow.path:
                # Re-evaluate trust threshold for this flow
                zone_s = C.get_zone(flow.s)
                zone_d = C.get_zone(flow.d)
                theta_path = self.pdp.get_theta_path(zone_s, zone_d, C)
                zone_node = C.get_zone(compromised_node)
                
                # Check if trust of node is below threshold
                if not self.pdp.evaluate_node(compromised_node, zone_node, theta_path, C):
                    print(f"[Controller] Flow {flow_id} compromised at hop {compromised_node}: trust score {self.pdp.get_trust_score(compromised_node, zone_node, C):.4f} < threshold {theta_path:.4f}")
                    affected_flow_ids.append(flow_id)

        for flow_id in affected_flow_ids:
            self.re_route_flow(flow_id, block_node=compromised_node)

    def re_route_flow(self, flow_id: str, block_node: str = None):
        """
        Re-routes an active flow.
        If a block_node is provided, we force the mask to exclude this node.
        If no alternative path is found, the flow is terminated.
        """
        flow = self.active_flows.get(flow_id)
        if not flow:
            return

        C = self.overlay_manager.get_c()
        s_str, d_str = flow.s, flow.d
        
        # Build masks
        struct_mask = self.bridge.get_struct_mask()
        node_masks = ActionMask.build_node_masks(C, self.pdp, s_str, d_str, struct_mask)
        
        # Force block compromised node if specified
        if block_node:
            node_masks[str(block_node)] = False

        # Get feasible edges
        E_f = ActionMask.get_feasible_edges(C, node_masks, self.zone_matrix)
        
        # Find paths P_f
        P_f = FeasiblePaths.find_paths(s_str, d_str, E_f)
        
        # Try to find new path
        new_path, reward = self.agent.select_path(s_str, d_str, P_f, C, self.bridge)
        
        if new_path:
            flow.path = new_path
            flow.status = "REROUTED"
            print(f"[Controller] Flow {flow_id} successfully re-routed. New Path={new_path}, Reward={reward:.2f}")
        else:
            flow.status = "TERMINATED"
            flow.path = []
            print(f"[Controller] Flow {flow_id} terminated: No alternative secure path available.")
