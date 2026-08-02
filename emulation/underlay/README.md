# Routed underlay

Thư mục này chỉ quản lý tầng WAN underlay. Nó không gán zone cho router và
không dùng router WAN như endpoint ứng dụng.

## Thành phần

- `model.py`: đọc SNDlib XML và matrix, lọc profile, scale và cấp địa chỉ.
- `frr.py`: sinh cấu hình OSPF cho từng router.
- `containernet_builder.py`: tạo router container, `TCLink`, IP, FRR,
  HTB→NetEm→CoDel và các probe packet-level.
- `validate.py`: kiểm tra tĩnh và xuất plan JSON, không cần quyền root.
- `run.py`: dựng packet-level underlay thật bằng Containernet.

## Luồng kiểm tra

```bash
source .venv/bin/activate
python emulation/scripts/fetch_underlay_dataset.py
python -m emulation.underlay.validate --profile mini
./emulation/scripts/build_underlay_image.sh
./emulation/scripts/deploy_underlay.sh mini --no-cli --load-response
```

Runtime chỉ dùng các artifact SNDlib được pin SHA-256 trong `underlay.yaml`:
topology Abilene XML, readme provenance, archive matrix sáu tháng và đúng member
`20040301-0010`. Parser đọc `preInstalledModule.capacity` với unit
`MBITPERSEC` và dừng nếu metadata không hợp lệ.

Chỉ chuyển sang profile `abilene` sau khi profile `mini` báo:

```text
UNDERLAY READY: 3 routers, 2 links, OSPF converged, all loopbacks reachable, iperf3=... Mbps
```

Hai profile đều dùng cùng cơ chế Docker/veth/TC/FRR:

- `mini`: 3 router/2 link, phù hợp để debug nhanh;
- `abilene`: toàn bộ 12 router/15 physical link của SNDlib.

Chúng không phải hai loại “mô phỏng” và “mạng thật”. Profile chỉ thay đổi quy
mô topology; packet forwarding ở cả hai đều diễn ra trong network namespace
thật của Linux.

Runtime evidence được ghi riêng theo profile trong
`emulation/runtime/underlay/<profile>/`:

- `configuration/underlay_plan.json`: source/checksum, capacity và propagation
  delay được dùng làm đầu vào tĩnh;
- `configuration/qdisc_applied.json`: HTB→NetEm→CoDel đã nạp lên từng egress;
- `measurements/routing_state.json`: địa chỉ và route OSPF quan sát khi chạy;
- `measurements/reachability.json`: output của packet ICMP thật;
- `measurements/iperf3_tcp.json`: throughput, tcpdump và interface-counter
  delta;
- `measurements/ditg_packet_metrics.json`: delay, jitter, throughput và loss
  do D-ITG receiver đo;
- `measurements/load_response.json`: UDP dưới/trên capacity, RTT khi có tải
  và qdisc drop delta (chỉ sinh khi có `--load-response`);
- `measurements/qdisc_counters_final.json`: counter đọc bằng `tc -s -d qdisc`
  sau tải.

Mỗi JSON có `artifact_class`. File `configuration` luôn có
`plot_eligible=false`; chỉ file `measurement` mới có `plot_eligible=true`.
Dashboard hoặc script vẽ đồ thị phải gọi guard trong `emulation/artifacts.py`
và không được dùng `delay_ms` trong plan như một kết quả đo.

## Nguồn của từng đại lượng

| Đại lượng | Nguồn/cơ chế |
|---|---|
| Node/link | SNDlib Abilene XML |
| Capacity | `preInstalledModule.capacity`, chia 100 |
| Demand | matrix SNDlib `20040301-0010`, chia 100 |
| Propagation delay cấu hình | Haversine × 2,1 / 204.000 km/s, nạp vào NetEm một lần trước khi đo |
| Queueing delay | phát sinh khi gói thật xếp hàng |
| Congestion loss | CoDel theo RFC 8289 |
| Random link loss | 0% |
| RTT/throughput/jitter/loss | ping, iperf3 và D-ITG đo khi chạy |

Không sinh đồ thị kết quả từ input Haversine. Configured delay phải ghi là
ước lượng được nạp vào hạ tầng; RTT, one-way delay D-ITG, throughput, jitter
và counter loss mới là số đo của lần chạy.

## Kết quả xác nhận gần nhất

Full profile đã dựng 12 router/15 link, OSPF hội tụ và 132/132 cặp loopback
reachable. 30 egress interface đều có CoDel. Trên link 24,8 Mbps:

| Offered load | Receiver | UDP loss | Concurrent RTT |
|---:|---:|---:|---:|
| 19,84 Mbps (80%) | 19,808 Mbps | 0% | 12,233 ms |
| 24,80 Mbps (100%) | 24,062 Mbps | 2,750% | 29,023 ms |
| 27,28 Mbps (110%) | 24,064 Mbps | 9,048% | 158,696 ms |

Điều này xác nhận capacity được thực thi, tải dưới capacity đi gần đủ, tải vượt
capacity phải chờ trong queue rồi bị CoDel drop; bandwidth cao không tự tạo
delay thấp nếu queue đang nghẽn.
