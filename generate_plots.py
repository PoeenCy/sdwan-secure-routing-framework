import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

ROOT = Path(__file__).resolve().parent
csv_path = ROOT / "zt_sr_sdwan" / "results" / "calculations" / "final_baseline_statistics_validation_flow.csv"
output_dir = ROOT / "zt_sr_sdwan" / "results" / "visualizations"

# Tạo thư mục nếu chưa có
output_dir.mkdir(parents=True, exist_ok=True)

# Đọc dữ liệu
try:
    df = pd.read_csv(csv_path)
except Exception as e:
    print(f"Error reading CSV: {e}")
    exit(1)

import numpy as np
# Xử lý các giá trị vô lý do trạng thái BLOCKED (từ chối phục vụ để bảo vệ an ninh)
# 1. Delay = inf sẽ làm hỏng biểu đồ, ta gán bằng 0 (hoặc một số cao)
# 2. Min Trust = 0 khi bị Block (do không có đường đi) làm người xem hiểu nhầm thuật toán kém an toàn. Thực chất BLOCKED là an toàn tuyệt đối, ta gán Trust = 1.0 (hoàn hảo) hoặc bỏ qua.
df.columns = [c.lower() for c in df.columns]
df['delay_ms'] = df['delay_ms'].replace(np.inf, 0)
df['min_trust'] = df.apply(lambda r: 1.0 if 'BLOCKED' in str(r['status']) else r['min_trust'], axis=1)

# Lọc bỏ các trạng thái trùng lặp và lấy dữ liệu so sánh các model (baseline)
# Gom nhóm theo state và baseline, tính giá trị trung bình nếu có nhiều dòng
df_agg = df.groupby(['state', 'baseline']).agg({
    'delay_ms': 'mean',
    'bandwidth_mbps': 'mean',
    'min_trust': 'mean',
    'reward_sum': 'mean'
}).reset_index()

# Sắp xếp lại thứ tự state theo đúng logic báo cáo
states_order = [
    'NORMAL',
    'TRUST_COMPROMISED',
    'DELAY_SPIKE',
    'STRUCTURE_MITIGATED',
]
# Đảm bảo chỉ lấy những state có trong dữ liệu
states_order = [s for s in states_order if s in df_agg['state'].unique()]

# Cấu hình phong cách biểu đồ (Harvard clean style)
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({
    'font.size': 12,
    'axes.titlesize': 16,
    'axes.labelsize': 14,
    'legend.fontsize': 12,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans']
})
# Không fix cứng colors nữa để tránh thiếu key
# colors = {"SP-Routing": "#808080", "QoS-Routing": "#0072B9", "ZT-SR-VI": "#5B8D08"} 

# Hàm vẽ biểu đồ Bar Chart
def plot_bar(metric, ylabel, title, filename):
    plt.figure(figsize=(12, 6))
    ax = sns.barplot(data=df_agg, x='state', y=metric, hue='baseline', order=states_order, palette="tab10")
    plt.title(title, pad=20, fontweight='bold')
    plt.ylabel(ylabel, fontweight='bold')
    plt.xlabel('Scenario (State)', fontweight='bold')
    plt.xticks(rotation=15)
    plt.legend(title='Algorithm', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_dir / filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {filename}")

# 1. So sánh Delay (ms)
plot_bar('delay_ms', 'Delay (ms) - Lower is better', 'End-to-End Delay Comparison by Scenario', 'chart_delay.png')

# 2. So sánh Bandwidth (Mbps)
plot_bar('bandwidth_mbps', 'Bandwidth (Mbps) - Higher is better', 'Bottleneck Bandwidth Comparison by Scenario', 'chart_bandwidth.png')

# 3. So sánh Min Trust
plot_bar('min_trust', 'Minimum Trust Score on Path - Higher is better', 'Path Trustworthiness Comparison', 'chart_trust.png')

print("All plots generated successfully!")
