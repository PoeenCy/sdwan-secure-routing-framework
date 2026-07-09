import sys
import csv
from pathlib import Path
try:
    from scapy.all import rdpcap, IP, TCP, UDP
except ImportError:
    print("Please install scapy: pip install scapy")
    sys.exit(1)

def parse_pcap_to_csv(pcap_file: Path, output_csv: Path):
    print(f"Reading massive PCAP file: {pcap_file}")
    print("This may take a long time for CAIDA Traces (GBs of data)...")
    
    if not pcap_file.exists():
        print(f"Error: {pcap_file} does not exist.")
        print("Please download CAIDA Anonymized Internet Traces from https://www.caida.org/catalog/datasets/passive_dataset/")
        print("You must sign the Acceptable Use Policy (AUP) to get access.")
        sys.exit(1)
        
    packets = rdpcap(str(pcap_file))
    print(f"Successfully loaded {len(packets)} packets into memory.")
    
    # Very basic flow reconstruction for ZT-SR
    # A real implementation would group packets by 5-tuple and calculate Inter-Arrival Time (Jitter) and RTT
    flows = {}
    
    for pkt in packets:
        if IP in pkt:
            src = pkt[IP].src
            dst = pkt[IP].dst
            proto = pkt[IP].proto
            length = len(pkt)
            time = float(pkt.time)
            
            flow_id = f"{src}-{dst}-{proto}"
            if flow_id not in flows:
                flows[flow_id] = {'packets': 0, 'bytes': 0, 'start_time': time, 'end_time': time}
            
            flows[flow_id]['packets'] += 1
            flows[flow_id]['bytes'] += length
            flows[flow_id]['end_time'] = time

    print(f"Extracted {len(flows)} unique traffic flows. Generating CSV...")
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["latency", "bandwidth", "packet_loss", "jitter"])
        
        for flow_id, stats in flows.items():
            duration = stats['end_time'] - stats['start_time']
            if duration <= 0:
                duration = 0.001
            
            # Simple heuristic mapping to our 4 variables
            bandwidth_bps = (stats['bytes'] * 8) / duration
            bandwidth_mbps = bandwidth_bps / 1_000_000
            
            # Simulating latency based on packet count and duration (rough estimate)
            latency = min(200.0, max(5.0, 1000.0 / (stats['packets'] / duration)))
            
            # Simulated loss and jitter
            loss = 0.001 * (bandwidth_mbps / 100.0) # Higher bandwidth = slightly more likely loss in CAIDA core traces
            jitter = latency * 0.1
            
            writer.writerow([latency, bandwidth_mbps, loss, jitter])
            
    print(f"Successfully wrote parsed flow statistics to {output_csv}")

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    pcap = base_dir / "data" / "traffic" / "caida_sample.pcap"
    out_csv = base_dir / "data" / "traffic" / "caida.csv"
    
    parse_pcap_to_csv(pcap, out_csv)
