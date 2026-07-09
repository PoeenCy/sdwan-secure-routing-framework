import os
import csv
import json
import math
import random
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Setup paths
base_dir = Path(__file__).resolve().parent.parent
data_dir = base_dir / "data"
nvd_dir = data_dir / "nvd"
traffic_dir = data_dir / "traffic"

nvd_dir.mkdir(parents=True, exist_ok=True)
traffic_dir.mkdir(parents=True, exist_ok=True)

nvd_file = nvd_dir / "cve_dataset.json"
caida_file = traffic_dir / "caida.csv"

load_dotenv(base_dir / ".env")
api_key = os.environ.get("NVD_API_KEY")

def download_nvd():
    print("Downloading NVD Dataset...")
    devices = ["router", "web_server", "database", "windows", "vpn"]
    results = {}
    headers = {"apiKey": api_key} if api_key else {}
    
    for device in devices:
        print(f" - Querying NVD for: {device} (Max 2000 results)")
        url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch={device}&resultsPerPage=2000"
        results[device] = []
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                vulnerabilities = data.get('vulnerabilities', [])
                print(f"   -> Found {len(vulnerabilities)} CVEs in NVD response.")
                
                for item in vulnerabilities:
                    vuln = item.get('cve', {})
                    cve_id = vuln.get('id', '')
                    metrics = vuln.get('metrics', {})
                    cvss = 5.0
                    if 'cvssMetricV31' in metrics:
                        cvss = metrics['cvssMetricV31'][0]['cvssData']['baseScore']
                    elif 'cvssMetricV30' in metrics:
                        cvss = metrics['cvssMetricV30'][0]['cvssData']['baseScore']
                    elif 'cvssMetricV2' in metrics:
                        cvss = metrics['cvssMetricV2'][0]['cvssData']['baseScore']
                    results[device].append({"cve_id": cve_id, "cvss": float(cvss)})
                print(f"   -> Successfully extracted {len(results[device])} CVSS records for {device}.")
            else:
                print(f"   -> API Error: {resp.status_code}")
        except Exception as e:
            print(f"   -> Request failed: {e}")
        time.sleep(2)
        
    with open(nvd_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
    print(f"Saved NVD data to {nvd_file}")

def generate_caida():
    print("\nGenerating CAIDA Traffic Dataset (Log-Normal Distribution)...")
    with open(caida_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["latency", "bandwidth", "packet_loss", "jitter"])
        for i in range(100):
            latency = random.lognormvariate(math.log(20), 0.5)
            bandwidth = random.uniform(100.0, 1000.0)
            loss = random.paretovariate(3.0) / 100.0
            jitter = random.uniform(1.0, 5.0)
            writer.writerow([latency, bandwidth, loss, jitter])
    print(f"Saved CAIDA data to {caida_file}")

if __name__ == "__main__":
    download_nvd()
    generate_caida()
    print("\nData provisioning complete!")
