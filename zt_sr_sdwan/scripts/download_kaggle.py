import os
import pandas as pd
from pathlib import Path
import sys

try:
    from kaggle.api.kaggle_api_extended import KaggleApi
except ImportError:
    print("Please install kaggle API: pip install kaggle")
    sys.exit(1)

def download_and_format_kaggle():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    
    token = os.environ.get('KAGGLE_API_TOKEN')
    if token:
        print("Kaggle token detected in environment; value is hidden.")
    
    # Kaggle python package requires KAGGLE_KEY and KAGGLE_USERNAME in environment variables
    # If the user only gave a token, we must bypass the package or just run cli
    try:
        import subprocess
        print("Đang tải dữ liệu thực tế từ Kaggle...")
        result = subprocess.run(
            f"kaggle datasets download -d kandij/real-time-network-traffic-encryption-dataset --unzip -p {Path(__file__).resolve().parent.parent / 'data' / 'traffic'}", 
            shell=True, 
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("Lỗi Kaggle API (403):")
            print(result.stderr)
            print("\nLÝ DO: Mã API Key của Kaggle bắt buộc phải đi kèm Username. Hoặc Dataset này yêu cầu bạn phải bấm 'Accept Rules' trên trang chủ Kaggle trước khi tải qua API.")
            sys.exit(1)
    except Exception as e:
        print(f"Kaggle Authentication failed: {e}")
        sys.exit(1)

    download_dir = Path(__file__).resolve().parent.parent / "data" / "traffic"
    download_dir.mkdir(parents=True, exist_ok=True)

    # Process the downloaded CSV to match our ZT-SR format (latency, bandwidth, packet_loss, jitter)
    print("Formatting dataset for ZT-SR...")
    for f in download_dir.glob("*.csv"):
        if "caida.csv" not in f.name:
            try:
                # The Kaggle dataset has columns like 'Jitter', 'Latency', 'Packet Loss', 'Throughput'
                df = pd.read_csv(f)
                
                # Create a new mapped dataframe
                new_df = pd.DataFrame()
                
                # Try to map column names intelligently
                cols = [c.lower() for c in df.columns]
                
                # Latency mapping
                lat_col = next((c for c in df.columns if 'latency' in c.lower() or 'delay' in c.lower()), None)
                new_df['latency'] = df[lat_col] if lat_col else df.iloc[:, 0]
                
                # Bandwidth mapping
                bw_col = next((c for c in df.columns if 'throughput' in c.lower() or 'bandwidth' in c.lower()), None)
                new_df['bandwidth'] = df[bw_col] if bw_col else df.iloc[:, 1]
                
                # Loss mapping
                loss_col = next((c for c in df.columns if 'loss' in c.lower() or 'drop' in c.lower()), None)
                new_df['packet_loss'] = df[loss_col] if loss_col else df.iloc[:, 2]
                
                # Jitter mapping
                jitter_col = next((c for c in df.columns if 'jitter' in c.lower()), None)
                new_df['jitter'] = df[jitter_col] if jitter_col else df.iloc[:, 3]
                
                # Save as our standard caida.csv
                target_file = download_dir / "caida.csv"
                new_df.to_csv(target_file, index=False)
                
                print(f"Successfully processed {len(new_df)} rows of REAL network traffic data.")
                print(f"Saved to {target_file}")
                
                # Cleanup the original kaggle csv to save space
                f.unlink()
                break
            except Exception as e:
                print(f"Error processing CSV: {e}")

if __name__ == "__main__":
    download_and_format_kaggle()
