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

def main():
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    topo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "topologies", "internetmci.graphml"))
    
    # 1. Setup framework components
    overlay = OverlayManager(config_dir, topo_path)
    pdp = PDP(config_dir)
    zm = ZoneMatrix(config_dir)
    bridge = CGBridge(zm, k=1.0)
    
    # Set default clean state for nodes
    pdp.use_avod_context = False
    for zone in pdp.context.profiles:
        pdp.context.profiles[zone]['cvss'] = 0.0
    for node in overlay.get_c().nodes():
        n_str = str(node)
        pdp.identity.set_score(n_str, 1.0)
        pdp.context.set_patch_factor(n_str, 1.0)
        pdp.behavior.set_score(n_str, 0.95)
        
    C = overlay.get_c()
    bridge.regenerate_g(C)
    G = bridge.G
    
    # Define artifact target path
    artifact_dir = r"C:\Users\thanhnha\.gemini\antigravity-ide\brain\44d54a0a-baed-4bc7-98e1-f62208eb4138"
    os.makedirs(artifact_dir, exist_ok=True)
    
    # Define local project results path
    results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results"))
    os.makedirs(results_dir, exist_ok=True)
    
    # Zone colors configuration
    zone_colors = {
        'Core': '#2f80ed', # Blue
        'DMZ': '#eb5757',  # Red
        'FIN': '#27ae60',  # Green
        'HR': '#f2994a',   # Orange
        'IT': '#9b51e0'    # Purple
    }
    
    # Common layout positions for node-to-node mapping compatibility
    pos = nx.kamada_kawai_layout(C)
    
    # ----------------------------------------------------
    # PLOT 1: CONNECTIVITY GRAPH C
    # ----------------------------------------------------
    plt.figure(figsize=(10, 8))
    
    node_colors_c = [zone_colors.get(C.get_zone(n), '#828282') for n in C.nodes()]
    
    # Draw C Nodes
    nx.draw_networkx_nodes(C, pos, node_size=600, node_color=node_colors_c, edgecolors='#333333', linewidths=1.5)
    
    # Draw C Edges
    nx.draw_networkx_edges(C, pos, edgelist=list(C.edges()), edge_color='#bdc3c7', 
                           arrows=True, arrowsize=12, width=1.0, connectionstyle="arc3,rad=0.1")
    
    # Draw Labels
    labels_c = {n: f"{n}\n({C.get_zone(n)})" for n in C.nodes()}
    nx.draw_networkx_labels(C, pos, labels=labels_c, font_size=8, font_family='sans-serif', font_weight='bold')
    
    # Legend
    for zone, color in zone_colors.items():
        plt.scatter([], [], c=color, label=zone, s=100, edgecolors='#333333', linewidths=1.0)
    plt.legend(scatterpoints=1, labelspacing=1, title='Network Zones', loc='upper right', frameon=True)
    
    plt.title("Connectivity Graph C (SD-WAN Overlay Network)", fontsize=14, fontweight='bold', pad=15)
    plt.axis('off')
    plt.tight_layout()
    
    c_img_path = os.path.join(artifact_dir, "graph_c_visualization.png")
    c_local_path = os.path.join(results_dir, "graph_c_visualization.png")
    plt.savefig(c_local_path, dpi=300, bbox_inches='tight')
    try:
        plt.savefig(c_img_path, dpi=300, bbox_inches='tight')
    except PermissionError:
        print(f"Skipping artifact copy, permission denied: {c_img_path}")
    plt.close()
    print(f"Graph C saved at: {c_img_path} and {c_local_path}")
    
    # ----------------------------------------------------
    # PLOT 2: ATTACK GRAPH G
    # ----------------------------------------------------
    plt.figure(figsize=(10, 8))
    
    node_colors_g = [zone_colors.get(G.nodes[n].get('zone'), '#828282') for n in G.nodes()]
    
    # Draw G Nodes
    nx.draw_networkx_nodes(G, pos, node_size=600, node_color=node_colors_g, edgecolors='#333333', linewidths=1.5)
    
    # Highlight root nodes R_G and target nodes L_G.
    entry_nodes = list(G.entry_nodes)
    target_nodes = list(G.target_nodes)
    
    nx.draw_networkx_nodes(G, pos, nodelist=entry_nodes, node_size=750, 
                           node_color='none', edgecolors='#eb5757', linewidths=2.5, label='Root Node (R_G)')
    nx.draw_networkx_nodes(G, pos, nodelist=target_nodes, node_size=750, 
                           node_color='none', edgecolors='#27ae60', linewidths=2.5, label='Target Asset (L_G)')
    
    # Highlight structural outliers (BN or MOD above Z-score threshold)
    struct_mask = bridge.get_struct_mask()
    outliers = [n for n in G.nodes() if not struct_mask.get(str(n), True)]
    
    nx.draw_networkx_nodes(G, pos, nodelist=outliers, node_size=600, 
                           node_color='none', edgecolors='#f2c94c', linewidths=2.0)
    
    # Draw G Edges (vulnerability propagation links)
    nx.draw_networkx_edges(G, pos, edgelist=list(G.edges()), edge_color='#e74c3c', 
                           arrows=True, arrowsize=12, width=1.2, connectionstyle="arc3,rad=0.1")
    
    # Draw Labels
    labels_g = {n: f"{n}\n({G.nodes[n].get('zone')})" for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels_g, font_size=8, font_family='sans-serif', font_weight='bold')
    
    # Custom legends for G
    for zone, color in zone_colors.items():
        plt.scatter([], [], c=color, label=zone, s=80, edgecolors='#333333', linewidths=1.0)
    plt.plot([], [], color='none', marker='o', markersize=10, markeredgecolor='#eb5757', markeredgewidth=2.0, label='Root Node (R_G)')
    plt.plot([], [], color='none', marker='o', markersize=10, markeredgecolor='#27ae60', markeredgewidth=2.0, label='Target Asset (L_G)')
    plt.plot([], [], color='none', marker='o', markersize=8, markeredgecolor='#f2c94c', markeredgewidth=1.5, ls='dashed', label='Struct Outlier')
    
    plt.legend(scatterpoints=1, labelspacing=0.8, title='Attack Graph Legend', loc='upper right', frameon=True)
    
    plt.title("Attack Graph G (Vulnerability Propagation Model)", fontsize=14, fontweight='bold', pad=15)
    plt.axis('off')
    plt.tight_layout()
    
    g_img_path = os.path.join(artifact_dir, "graph_g_visualization.png")
    g_local_path = os.path.join(results_dir, "graph_g_visualization.png")
    plt.savefig(g_local_path, dpi=300, bbox_inches='tight')
    try:
        plt.savefig(g_img_path, dpi=300, bbox_inches='tight')
    except PermissionError:
        print(f"Skipping artifact copy, permission denied: {g_img_path}")
    plt.close()
    print(f"Graph G saved at: {g_img_path} and {g_local_path}")

if __name__ == "__main__":
    main()
