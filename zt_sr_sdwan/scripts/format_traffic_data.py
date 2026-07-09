import pandas as pd
from pathlib import Path

# Paths
base_dir = Path(r"d:\SD_WAN_Secure_Routing\zt_sr_sdwan")
input_file = base_dir / "data" / "network_traffic_dataset.csv"
output_file = base_dir / "data" / "traffic" / "caida.csv"

print(f"Reading from: {input_file}")
df = pd.read_csv(input_file)

zt_df = pd.DataFrame()
zt_df['latency'] = df['latency']
zt_df['bandwidth'] = df['throughput']
zt_df['packet_loss'] = df['packet_loss'] / 100.0  
zt_df['jitter'] = df['jitter']

zt_df = zt_df.fillna(0)
zt_df['packet_loss'] = zt_df['packet_loss'].clip(lower=0.0, upper=1.0)

output_file.parent.mkdir(parents=True, exist_ok=True)
zt_df.to_csv(output_file, index=False)

print(f"Success! Processed {len(zt_df)} rows of network traffic.")
print(f"Saved correctly formatted data to: {output_file}")
