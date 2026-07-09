from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = ROOT / "docs" / "assets"
RESULT_CSV = ROOT / "zt_sr_sdwan" / "results" / "calculations" / "final_baseline_statistics_validation_flow.csv"


def _save(fig, filename):
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(ASSET_DIR / filename, dpi=220, bbox_inches="tight")
    plt.close(fig)


def draw_pipeline():
    fig, ax = plt.subplots(figsize=(18, 5))
    ax.axis("off")

    steps = [
        ("Input", "Topology\nZone policy\nTrust/CVE config"),
        ("Graph C", "Connectivity graph\nQoS edges\nZone labels"),
        ("Metric C", "Exposure metrics\nTINR / MPL / CD\nQoS weights"),
        ("Graph G", "Attack graph\nRoot R_G\nTarget L_G"),
        ("Metric G", "MSPL / NSP\nBN / AB\nMOD / CMC"),
        ("Trust + Mask", "PDP trust score\nZone matrix\nAction mask"),
        ("Routing", "SP / QoS / Seg\nZT / ZT-SR-VI"),
        ("Output", "CSV tables\nCharts\nPath figures"),
    ]

    left = 0.03
    right = 0.97
    box_w = 0.095
    x_gap = (right - left - box_w * len(steps)) / (len(steps) - 1)
    box_h = 0.42
    y = 0.45

    for idx, (title, desc) in enumerate(steps):
        x = left + idx * (box_w + x_gap)
        color = "#e8f1ff" if idx % 2 == 0 else "#eef8ee"
        rect = plt.Rectangle((x, y), box_w, box_h, facecolor=color, edgecolor="#2f3b52", linewidth=1.3)
        ax.add_patch(rect)
        ax.text(x + box_w / 2, y + box_h - 0.07, title, ha="center", va="top", fontsize=10.7, fontweight="bold")
        ax.text(x + box_w / 2, y + 0.08, desc, ha="center", va="bottom", fontsize=8.2)
        if idx < len(steps) - 1:
            arrow_margin = min(0.006, x_gap / 3)
            ax.annotate(
                "",
                xy=(x + box_w + x_gap - arrow_margin, y + box_h / 2),
                xytext=(x + box_w + arrow_margin, y + box_h / 2),
                arrowprops=dict(arrowstyle="->", lw=1.4, color="#2f3b52"),
            )

    ax.text(
        0.5,
        0.18,
        "Luồng xử lý: dữ liệu mạng -> hai tầng đồ thị -> chỉ số bảo mật/trust -> lọc hành động -> so sánh đường đi",
        ha="center",
        va="center",
        fontsize=11,
        color="#2f3b52",
    )
    _save(fig, "pipeline_quy_trinh.png")


def draw_two_layer_graph():
    fig, axes = plt.subplots(2, 1, figsize=(12, 6.4), gridspec_kw={"height_ratios": [1.15, 1]})

    c_graph = nx.DiGraph()
    c_edges = [
        ("14", "8"),
        ("8", "6"),
        ("6", "5"),
        ("14", "12"),
        ("12", "0"),
        ("0", "6"),
        ("0", "7"),
        ("7", "5"),
    ]
    c_graph.add_edges_from(c_edges)
    c_pos = {
        "14": (0, 0),
        "8": (1.25, 0.65),
        "6": (2.5, 0.65),
        "5": (3.75, 0.65),
        "12": (1.05, -0.55),
        "0": (2.2, -0.55),
        "7": (3.2, -0.55),
    }

    g_graph = nx.DiGraph()
    g_graph.add_edges_from([("14", "8"), ("8", "6"), ("6", "5")])
    g_pos = {"14": (0, 0), "8": (1.25, 0), "6": (2.5, 0), "5": (3.75, 0)}

    ax = axes[0]
    ax.set_title("Tầng 1 - Graph C: topology định tuyến và QoS", fontsize=13, fontweight="bold")
    ax.axis("off")
    node_colors = ["#f6d365" if n in {"8", "6"} else "#d9e8ff" for n in c_graph.nodes()]
    nx.draw_networkx_nodes(c_graph, c_pos, node_color=node_colors, node_size=1150, edgecolors="#24324a", ax=ax)
    nx.draw_networkx_labels(c_graph, c_pos, font_weight="bold", ax=ax)
    nx.draw_networkx_edges(c_graph, c_pos, edgelist=c_edges, arrows=True, arrowstyle="-|>", width=1.4, edge_color="#77839a", ax=ax)
    nx.draw_networkx_edges(c_graph, c_pos, edgelist=[("14", "8"), ("8", "6"), ("6", "5")], arrows=True, arrowstyle="-|>", width=3.2, edge_color="#d62728", ax=ax)
    nx.draw_networkx_edges(c_graph, c_pos, edgelist=[("14", "12"), ("12", "0"), ("0", "6"), ("6", "5")], arrows=True, arrowstyle="-|>", width=2.4, edge_color="#2ca02c", ax=ax)
    ax.text(0, -1.05, "Đỏ: path ngắn 14->8->6->5 | Xanh: path thay thế 14->12->0->6->5", fontsize=10)
    ax.set_xlim(-0.35, 4.1)
    ax.set_ylim(-1.25, 1.05)

    ax = axes[1]
    ax.set_title("Tầng 2 - Graph G: đường tấn công dùng để tính BN/AB", fontsize=13, fontweight="bold")
    ax.axis("off")
    node_colors = ["#ffdf8a" if n in {"8", "6"} else "#e5f3e5" for n in g_graph.nodes()]
    nx.draw_networkx_nodes(g_graph, g_pos, node_color=node_colors, node_size=1150, edgecolors="#24324a", ax=ax)
    nx.draw_networkx_labels(g_graph, g_pos, font_weight="bold", ax=ax)
    nx.draw_networkx_edges(g_graph, g_pos, arrows=True, arrowstyle="-|>", width=3.0, edge_color="#d62728", ax=ax)
    ax.text(0.05, -0.42, "R_G = {14}; L_G = {6, 5}; BN(8)=2, BN(6)=1, AB_G=0.5", fontsize=10)
    ax.set_xlim(-0.35, 4.1)
    ax.set_ylim(-0.65, 0.45)

    fig.suptitle("Hai tầng đồ thị: C quyết định đường đi, G đo rủi ro/chokepoint", fontsize=15, fontweight="bold")
    fig.subplots_adjust(top=0.86, hspace=0.55)
    _save(fig, "two_layer_graph_c_g.png")


def draw_scenario_paths():
    df = pd.read_csv(RESULT_CSV)
    order = ["NORMAL", "BW_CONGESTION", "TRUST_DEGRADED", "DELAY_SPIKE", "STRUCTURE_MITIGATED"]
    chosen = df[df["Baseline"].isin(["SP-Routing", "QoS-Routing", "ZT-Routing", "ZT-SR-VI"])].copy()
    chosen["State"] = pd.Categorical(chosen["State"], categories=order, ordered=True)
    chosen = chosen.sort_values(["State", "Baseline"])

    fig, ax = plt.subplots(figsize=(15, 8))
    ax.axis("off")
    ax.set_title("Đường đi của flow 14 -> 5 theo từng kịch bản", fontsize=15, fontweight="bold", pad=18)

    states = [s for s in order if s in set(chosen["State"].astype(str))]
    baselines = ["SP-Routing", "QoS-Routing", "ZT-Routing", "ZT-SR-VI"]
    col_left = 0.2
    col_w = (0.97 - col_left) / len(baselines)
    row_h = 0.145

    ax.text(0.03, 0.94, "State", fontweight="bold", fontsize=10)
    for j, bl in enumerate(baselines):
        ax.text(col_left + 0.02 + j * col_w, 0.94, bl, fontweight="bold", fontsize=10)

    for i, state in enumerate(states):
        y = 0.84 - i * row_h
        state_label = {
            "BW_CONGESTION": "BW\nCONGESTION",
            "TRUST_DEGRADED": "TRUST\nDEGRADED",
            "DELAY_SPIKE": "DELAY\nSPIKE",
            "STRUCTURE_MITIGATED": "STRUCTURE\nMITIGATED",
        }.get(state, state)
        ax.text(0.03, y, state_label, fontsize=9.6, fontweight="bold", va="top")
        rows = chosen[chosen["State"].astype(str) == state]
        for j, bl in enumerate(baselines):
            row = rows[rows["Baseline"] == bl]
            if row.empty:
                text = "-"
                color = "#f5f5f5"
            else:
                r = row.iloc[0]
                if r["Status"] != "ACTIVE":
                    text = "BLOCKED"
                    color = "#ffe2e2"
                else:
                    text = f"{r['Path']}\nDelay={float(r['Delay_ms']):.1f} ms | BN={float(r['Avg_BN_on_path']):.2f}"
                    color = "#eaf5ff" if float(r["Avg_BN_on_path"]) >= 0.7 else "#eef8ee"
            x = col_left + j * col_w
            rect = plt.Rectangle((x - 0.01, y - row_h + 0.02), col_w - 0.02, row_h - 0.025, facecolor=color, edgecolor="#b7bdc8", linewidth=0.8)
            ax.add_patch(rect)
            ax.text(x + (col_w - 0.02) / 2, y - 0.035, text, fontsize=8.1, va="top", ha="center")

    ax.text(
        0.03,
        0.035,
        "Màu xanh nhạt: path đi qua node BN cao hơn. Màu xanh lá: path tránh chokepoint hơn. Màu đỏ: bị chặn bởi trust/zone/action mask.",
        fontsize=9.5,
        color="#2f3b52",
    )
    _save(fig, "scenario_path_matrix.png")


def draw_state_graph_paths():
    base_edges = [
        ("14", "8"),
        ("8", "6"),
        ("6", "5"),
        ("14", "12"),
        ("12", "0"),
        ("0", "6"),
        ("0", "7"),
        ("7", "5"),
    ]
    pos = {
        "14": (0, 0),
        "8": (1.25, 0.7),
        "6": (2.5, 0.7),
        "5": (3.75, 0.7),
        "12": (1.05, -0.6),
        "0": (2.2, -0.6),
        "7": (3.2, -0.6),
    }
    graph = nx.DiGraph()
    graph.add_edges_from(base_edges)

    def path_edges(path):
        return list(zip(path[:-1], path[1:]))

    panels = [
        {
            "title": "NORMAL",
            "note": "SP/QoS/ZT: nhanh nhưng BN cao\nZT-SR-VI: path thay thế BN thấp",
            "paths": [
                (["14", "8", "6", "5"], "#d62728", "SP/QoS/ZT"),
                (["14", "12", "0", "6", "5"], "#2ca02c", "ZT-SR-VI"),
            ],
            "node_colors": {},
        },
        {
            "title": "BW_CONGESTION",
            "note": "14->8 còn delay thấp nhưng bw=10 Mbps\nQoS/ZT-SR-VI chuyển path",
            "paths": [
                (["14", "8", "6", "5"], "#d62728", "SP/ZT"),
                (["14", "12", "0", "6", "5"], "#2ca02c", "QoS/ZT-SR-VI"),
            ],
            "edge_notes": [("14", "8", "bw=10")],
            "node_colors": {},
        },
        {
            "title": "TRUST_DEGRADED",
            "note": "Node 6: trust=0.79 < 0.90\nZT né qua 7; ZT-SR-VI blocked",
            "paths": [
                (["14", "8", "6", "5"], "#d62728", "SP/QoS"),
                (["14", "12", "0", "7", "5"], "#9467bd", "ZT"),
            ],
            "node_colors": {"6": "#ffd6d6"},
        },
        {
            "title": "DELAY_SPIKE",
            "note": "Edge 14->8 bị spike delay\nTất cả chuyển sang path thay thế",
            "paths": [
                (["14", "12", "0", "6", "5"], "#2ca02c", "All baselines"),
            ],
            "edge_notes": [("14", "8", "delay spike")],
            "node_colors": {},
        },
        {
            "title": "STRUCTURE_MITIGATED",
            "note": "Edge 8->6 bị vô hiệu hóa\nTất cả đi qua 12->0->6",
            "paths": [
                (["14", "12", "0", "6", "5"], "#2ca02c", "All baselines"),
            ],
            "disabled_edges": [("8", "6")],
            "node_colors": {},
        },
    ]

    fig, axes = plt.subplots(2, 3, figsize=(15, 8.2))
    flat_axes = axes.flatten()

    for ax, panel in zip(flat_axes, panels):
        ax.axis("off")
        ax.set_title(panel["title"], fontsize=12.5, fontweight="bold")
        node_colors = [panel.get("node_colors", {}).get(node, "#d9e8ff") for node in graph.nodes()]
        nx.draw_networkx_nodes(graph, pos, node_color=node_colors, node_size=700, edgecolors="#24324a", ax=ax)
        nx.draw_networkx_labels(graph, pos, font_weight="bold", font_size=9.5, ax=ax)
        nx.draw_networkx_edges(graph, pos, edgelist=base_edges, arrows=True, arrowstyle="-|>", width=1.1, edge_color="#b3bdcc", ax=ax)

        for path, color, label in panel["paths"]:
            nx.draw_networkx_edges(
                graph,
                pos,
                edgelist=path_edges(path),
                arrows=True,
                arrowstyle="-|>",
                width=3.1,
                edge_color=color,
                ax=ax,
                label=label,
            )

        for edge in panel.get("disabled_edges", []):
            u, v = edge
            x = (pos[u][0] + pos[v][0]) / 2
            y = (pos[u][1] + pos[v][1]) / 2
            ax.text(x, y + 0.08, "X", color="#111111", fontsize=16, fontweight="bold", ha="center", va="center")

        for u, v, label in panel.get("edge_notes", []):
            x = (pos[u][0] + pos[v][0]) / 2
            y = (pos[u][1] + pos[v][1]) / 2
            ax.text(x, y + 0.18, label, color="#7f1d1d", fontsize=8.5, fontweight="bold", ha="center")

        ax.text(0.02, -0.22, panel["note"], transform=ax.transAxes, fontsize=8.5, va="top", color="#2f3b52")
        ax.set_xlim(-0.35, 4.1)
        ax.set_ylim(-1.15, 1.15)

    legend_ax = flat_axes[-1]
    legend_ax.axis("off")
    legend_ax.set_title("Cách đọc", fontsize=12.5, fontweight="bold")
    legend_ax.text(
        0.02,
        0.78,
        "Đỏ: path nhanh nhưng đi qua chokepoint BN cao.\n"
        "Xanh: path thay thế/mitigated có Avg BN thấp hơn.\n"
        "Tím: path Zero Trust né node không đạt trust.\n"
        "X: edge bị vô hiệu hóa trong kịch bản structure.",
        fontsize=10,
        va="top",
        color="#2f3b52",
    )
    legend_ax.text(
        0.02,
        0.28,
        "Nguồn dữ liệu: final_baseline_statistics_validation_flow.csv",
        fontsize=9,
        color="#2f3b52",
    )

    fig.suptitle("Path của flow 14 -> 5 được overlay trực tiếp trên graph C", fontsize=15, fontweight="bold")
    fig.subplots_adjust(top=0.88, hspace=0.7, wspace=0.28)
    _save(fig, "scenario_graph_paths.png")


def main():
    draw_pipeline()
    draw_two_layer_graph()
    draw_scenario_paths()
    draw_state_graph_paths()
    print(f"Generated explanatory diagrams in {ASSET_DIR}")


if __name__ == "__main__":
    main()
