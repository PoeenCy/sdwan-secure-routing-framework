# Packet-level emulation

Đây là phần triển khai packet-level của framework.

## Phân lớp thư mục

```text
emulation/
├── config/
│   └── underlay.yaml       # topology, IP pool, TC, D-ITG và OSPF
├── underlay/
│   ├── model.py            # SNDlib XML + traffic matrix -> routed plan
│   ├── frr.py              # cấu hình OSPF
│   ├── containernet_builder.py
│   ├── validate.py
│   └── run.py
├── images/router/          # router container có FRR, iperf3 và D-ITG
├── scripts/
├── tests/
└── runtime/                # manifest/log sinh khi chạy, không commit
```

## Parrot OS và virtual environment

Python project chạy trong `.venv`. Docker daemon, Open vSwitch, `mnexec`,
network namespace và kernel module không thể nằm trong Python virtual
environment; chúng phải được cài ở host và topology phải chạy với quyền root.

Lệnh `docker` mặc định của một số bản Parrot là wrapper của Podman. Preflight
sẽ từ chối wrapper này thay vì báo deployment thành công giả.

Dataset underlay runtime được tải bằng
`emulation/scripts/fetch_underlay_dataset.py` và kiểm tra SHA-256. Deployment
chỉ nhận SNDlib XML/matrix đã ghim và từ chối metadata thiếu hoặc sai.

## Underlay checkpoint

```bash
python3 -m venv .venv
source .venv/bin/activate
./emulation/scripts/bootstrap_parrot.sh
python emulation/scripts/fetch_underlay_dataset.py
./emulation/scripts/build_underlay_image.sh
./emulation/scripts/deploy_underlay.sh mini --no-cli --load-response
```

Hai giá trị `mini` và `abilene` là hai **profile quy mô** của cùng một
packet-level runtime, không phải lựa chọn giữa traffic giả và Docker thật:

| Profile | Quy mô | Mục đích |
|---|---:|---|
| `mini` | 3 router, 2 link | Kiểm tra nhanh Atlanta--Indianapolis--Chicago |
| `abilene` | 12 router, 15 physical link | Chạy toàn bộ SNDlib Abilene |

Cả hai profile tạo Docker container, veth/network namespace,
HTB→NetEm→CoDel và FRR/OSPF thật. Lệnh mặc định giữ CLI mở; `--no-cli` chạy
kiểm định rồi tự dọn topology. `--load-response` thêm phép tải UDP
80/100/110% trên link có capacity thấp nhất.

Trong CLI của profile `mini`:

```text
containernet> rATLAng vtysh -c "show ip ospf neighbor"
containernet> rATLAng vtysh -c "show ip route ospf"
containernet> rATLAng ping -c 3 10.255.0.2
containernet> rIPLSng tcpdump -ni any
```

Sau khi `mini` ổn định:

```bash
./emulation/scripts/deploy_underlay.sh abilene --no-cli --load-response
```

Không chuyển sang overlay nếu chưa có thông báo `UNDERLAY READY`.

Mỗi lần khởi chạy tự động kiểm tra đủ neighbor OSPF, route kernel, ping mọi cặp
loopback, một TCP flow iperf3 qua đường nhiều hop và một demand có giá trị lớn
nhất từ traffic matrix bằng D-ITG. Kết quả của mỗi profile được tách tại:

```text
emulation/runtime/underlay/<profile>/
├── underlay_plan.json
├── underlay_qdisc_initial.json
├── underlay_routing_state.json
├── underlay_reachability.json
├── underlay_traffic.json
├── underlay_ditg_traffic.json
├── underlay_load_response.json
└── underlay_qdisc_final.json
```

`underlay_traffic.json` chứa tcpdump và chênh lệch counter từng veth.
`underlay_ditg_traffic.json` chứa rate cấu hình từ demand cùng delay, jitter,
throughput và loss do D-ITG đo. `underlay_load_response.json` chứa throughput,
concurrent ping và CoDel drop ở ba mức tải.

## Cơ sở dữ liệu và giới hạn tuyên bố

- Topology/capacity lấy trực tiếp từ SNDlib XML. Capacity gốc 2.480/9.920
  Mbit/s được chia 100 thành 24,8/99,2 Mbit/s.
- Traffic matrix là epoch 5 phút `20040301-0010`, thành viên đầu tiên theo thời
  gian trong archive đã pin; demand cũng chia 100 để giữ tỷ lệ demand/capacity.
- Delay NetEm là **ước lượng propagation một chiều** từ tọa độ SNDlib,
  Haversine, stretch factor 2,1 và 204.000 km/s. Nó không phải delay đo sẵn
  trong SNDlib.
- Configured random loss bằng 0. Loss trong bài tải là congestion/AQM drop do
  CoDel, không phải physical link loss.
- D-ITG hiện chạy một demand lớn nhất như probe kiểm chứng underlay. Việc phát
  đồng thời toàn bộ 131 OD demand thuộc checkpoint workload ở tầng tiếp theo.
