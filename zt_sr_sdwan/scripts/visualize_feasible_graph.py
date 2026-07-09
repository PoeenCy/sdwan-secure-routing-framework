import os
import sys
import networkx as nx
import matplotlib.pyplot as plt

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.action_mask import ActionMask

def main():
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    topo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "topologies", "internetmci.graphml"))
    
    # 1. Setup framework components
    overlay = OverlayManager(config_dir, topo_path)
    pdp = PDP(config_dir)
    zm = ZoneMatrix(config_dir)
    bridge = CGBridge(zm, k=1.0) # Standard Z-score parameter
    
    # Setup clean posture
    pdp.use_avod_context = False
    for zone in pdp.context.profiles:
        pdp.context.profiles[zone]['cvss'] = 0.0
    for node in overlay.get_c().nodes():
        n_str = str(node)
        pdp.identity.set_score(n_str, 1.0)
        pdp.context.set_patch_factor(n_str, 1.0)
        pdp.behavior.set_score(n_str, 0.95)
        
    bridge.regenerate_g(overlay.get_c())
    C = overlay.get_c()
    
    # Define paths
    artifact_dir = r"C:\Users\thanhnha\.gemini\antigravity-ide\brain\44d54a0a-baed-4bc7-98e1-f62208eb4138"
    results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results"))
    os.makedirs(artifact_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)
    
    # 2. Get composite masks and feasible edges E_f for flow from IT '14' -> FIN '7'
    struct_mask = bridge.get_struct_mask()
    node_masks = ActionMask.build_node_masks(C, pdp, '14', '7', struct_mask)
    E_f = ActionMask.get_feasible_edges(C, node_masks, zm)
    
    # 3. Plot the Feasible/Sanitized Graph E_f
    plt.figure(figsize=(10, 8))
    pos = nx.kamada_kawai_layout(C)
    
    zone_colors = {
        'Core': '#2f80ed',
        'DMZ': '#eb5757',
        'FIN': '#27ae60',
        'HR': '#f2994a',
        'IT': '#9b51e0'
    }
    
    # Node colors list
    node_colors = []
    for node in C.nodes():
        node_str = str(node)
        # If the node is masked out (blocked), draw it in light gray to show it is disabled
        if not node_masks.get(node_str, True):
            node_colors.append('#bdc3c7')
        else:
            node_colors.append(zone_colors.get(C.get_zone(node), '#828282'))
            
    # Draw Nodes
    nx.draw_networkx_nodes(C, pos, node_size=600, node_color=node_colors, 
                           edgecolors=['#7f8c8d' if not node_masks.get(str(n), True) else '#333333' for n in C.nodes()], 
                           linewidths=1.5)
    
    # Separate feasible edges and blocked edges
    feasible_edgelist = list(E_f)
    all_edges = set(C.edges())
    blocked_edgelist = list(all_edges - E_f)
    
    # Draw feasible edges as green thick arrows
    nx.draw_networkx_edges(C, pos, edgelist=feasible_edgelist, edge_color='#27ae60', 
                           arrows=True, arrowsize=15, width=2.0, connectionstyle="arc3,rad=0.1", label='Feasible (Allowed)')
                           
    # Draw blocked/pruned edges as thin dashed light gray arrows
    nx.draw_networkx_edges(C, pos, edgelist=blocked_edgelist, edge_color='#e0e0e0', 
                           arrows=True, arrowsize=8, width=0.5, style='dashed', connectionstyle="arc3,rad=0.1", label='Pruned (Blocked)')
    
    # Draw Labels (strikethrough or grayed out for blocked nodes)
    labels = {}
    for node in C.nodes():
        node_str = str(node)
        zone = C.get_zone(node_str)
        if not node_masks.get(node_str, True):
            labels[node] = f"{node} [X]\n({zone})"
        else:
            labels[node] = f"{node}\n({zone})"
            
    nx.draw_networkx_labels(C, pos, labels=labels, font_size=8, font_family='sans-serif', font_weight='bold')
    
    # Legend
    for zone, color in zone_colors.items():
        plt.scatter([], [], c=color, label=zone, s=80, edgecolors='#333333', linewidths=1.0)
    plt.scatter([], [], c='#bdc3c7', label='Blocked Node', s=80, edgecolors='#7f8c8d', linewidths=1.0)
    plt.plot([], [], color='#27ae60', linewidth=2, label='Feasible Link')
    plt.plot([], [], color='#e0e0e0', linewidth=1, ls='dashed', label='Pruned Link')
    
    plt.legend(scatterpoints=1, labelspacing=0.8, title='Legend', loc='upper right', frameon=True)
    
    plt.title("Feasible Graph E_f (Sanitized Routing Topology)\nFlow IT '14' to FIN '7'", fontsize=14, fontweight='bold', pad=15)
    plt.axis('off')
    plt.tight_layout()
    
    img_path = os.path.join(artifact_dir, "feasible_graph_ef.png")
    local_path = os.path.join(results_dir, "feasible_graph_ef.png")
    plt.savefig(local_path, dpi=300, bbox_inches='tight')
    try:
        plt.savefig(img_path, dpi=300, bbox_inches='tight')
    except PermissionError:
        print(f"Skipping artifact copy, permission denied: {img_path}")
    plt.close()
    
    print(f"Feasible graph saved at: {img_path} and {local_path}")

if __name__ == "__main__":
    main()
