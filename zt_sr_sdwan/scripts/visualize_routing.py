import os
import sys
import networkx as nx

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.heuristic_agent import HeuristicAgent
from src.routing.baselines import Baselines

def main():
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    topo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "topologies", "internetmci.graphml"))
    
    # 1. Setup framework components
    overlay = OverlayManager(config_dir, topo_path)
    pdp = PDP(config_dir)
    zm = ZoneMatrix(config_dir)
    bridge = CGBridge(zm)
    agent = HeuristicAgent()
    
    # Configure clean posture for the visualization
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
    
    # 2. Get the optimal ZT-SR-VI path (S1: IT '14' -> FIN '7')
    path = Baselines.zt_sr_drl('14', '7', C, pdp, zm, bridge, agent)
    print(f"Optimal ZT-SR Path: {path}")

    # Try to import matplotlib to draw the graph
    try:
        import matplotlib.pyplot as plt
        print("Matplotlib is available. Generating visualization...")
    except ImportError:
        print("Matplotlib is not installed. Installing matplotlib...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib"])
        import matplotlib.pyplot as plt

    # 3. Create the drawing
    plt.figure(figsize=(12, 10))
    
    # Position nodes using Kamada-Kawai layout for a beautiful structural distribution
    pos = nx.kamada_kawai_layout(C)
    
    # Colors according to zones
    zone_colors = {
        'Core': '#2b7bba', # Blue
        'DMZ': '#e05c5c',  # Soft Red
        'FIN': '#42a868',  # Green
        'HR': '#f2994a',   # Orange
        'IT': '#9b51e0'    # Purple
    }
    
    # Build list of colors for each node
    node_colors = []
    for node in C.nodes():
        zone = C.get_zone(node)
        node_colors.append(zone_colors.get(zone, '#828282'))

    # Draw all nodes
    nx.draw_networkx_nodes(C, pos, node_size=700, node_color=node_colors, edgecolors='#333333', linewidths=1.5)
    
    # Draw all edges as light gray arrows
    nx.draw_networkx_edges(C, pos, edgelist=list(C.edges()), edge_color='#cccccc', 
                           arrows=True, arrowsize=15, width=1.0, connectionstyle="arc3,rad=0.1")

    # Draw labels
    labels = {node: f"{node}\n({C.get_zone(node)})" for node in C.nodes()}
    nx.draw_networkx_labels(C, pos, labels=labels, font_size=8, font_family='sans-serif', font_weight='bold')

    # Highlight the ZT-SR path if found
    if path:
        path_edges = list(zip(path[:-1], path[1:]))
        # Draw path edges in thick green
        nx.draw_networkx_edges(C, pos, edgelist=path_edges, edge_color='#27ae60', 
                               width=3.5, arrows=True, arrowsize=20, connectionstyle="arc3,rad=0.1")
        # Draw path nodes with gold highlights
        nx.draw_networkx_nodes(C, pos, nodelist=path, node_size=900, 
                               node_color=[zone_colors.get(C.get_zone(n)) for n in path],
                               edgecolors='#f2c94c', linewidths=3.0)

    # Create manual legend
    for zone, color in zone_colors.items():
        plt.scatter([], [], c=color, label=zone, s=100, edgecolors='#333333', linewidths=1.0)
    plt.legend(scatterpoints=1, labelspacing=1, title='Network Zones', loc='upper right', frameon=True, facecolor='#ffffff', edgecolor='#cccccc')

    plt.title("ZT-SR-SDWAN Path Routing Visualization\nIT '14' to FIN '7' (Path: " + str(path) + ")", 
              fontsize=14, fontweight='bold', pad=20)
    plt.axis('off')
    
    # Save the output image
    res_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results"))
    os.makedirs(res_dir, exist_ok=True)
    img_path = os.path.join(res_dir, "routing_path_visualization.png")
    
    plt.tight_layout()
    plt.savefig(img_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Visualization successfully saved at: {img_path}")

if __name__ == "__main__":
    main()
