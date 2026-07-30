# ZT-SR SD-WAN Packet-Level Framework

Kho mã nguồn triển khai môi trường SD-WAN bằng Docker/Containernet với packet
forwarding thật trong Linux network namespace. Phiên bản hiện tại tập trung vào
tầng WAN underlay có nguồn dữ liệu và cơ chế kiểm chứng tái lập được.

## Trạng thái

Tầng underlay đã hoàn thành:

- topology SNDlib Abilene: 12 router, 15 physical link;
- router Docker chạy FRRouting/OSPF;
- veth + Linux `tc`: HTB → NetEm → CoDel;
- capacity và demand đọc trực tiếp từ SNDlib rồi cùng chia 100;
- propagation delay ước lượng từ tọa độ, Haversine và mô hình sợi quang;
- random link loss bằng 0; congestion loss phát sinh từ CoDel;
- kiểm chứng bằng ping, iperf3, tcpdump, interface counter và D-ITG.

Kết quả full profile gần nhất: OSPF hội tụ, 132/132 cặp loopback reachable và
toàn bộ 30 egress interface có CoDel. Tải 80/100/110% trên link 24,8 Mbps cho
throughput nhận 19,808/24,062/24,064 Mbps và loss 0/2,750/9,048%.

Overlay CPE/tunnel, replay đồng thời toàn traffic matrix, Zero Trust controller,
Vulhub/Kali và Suricata là các checkpoint tiếp theo. Repository chưa chứa
placeholder cho các tầng này; chúng chỉ được thêm khi có implementation và
test.

## Cấu trúc

```text
.
├── emulation/
│   ├── config/                 # SNDlib, scaling, queue, routing và profile
│   ├── images/router/          # Docker image FRR + D-ITG
│   ├── scripts/                # bootstrap, fetch, build, deploy, cleanup
│   ├── tests/                  # kiểm thử parser và FRR
│   └── underlay/               # model, FRR, Containernet runtime và validation
├── docs/
│   └── phuong_phap_trien_khai_zt_sr_sdwan_containernet.md
├── .gitignore
└── README.md
```

Dataset tải về, runtime evidence, `.venv`, bản clone Containernet và cache
không được commit. URL, archive member và SHA-256 cần thiết để tái tạo chúng
được ghim trong `emulation/config/underlay.yaml`.

## Chạy trên Parrot OS

Khởi tạo môi trường:

```bash
python3 -m venv .venv
source .venv/bin/activate
./emulation/scripts/bootstrap_parrot.sh
./emulation/scripts/build_underlay_image.sh
```

Kiểm tra nhanh:

```bash
./emulation/scripts/deploy_underlay.sh mini --no-cli --load-response
```

Chạy toàn bộ Abilene:

```bash
./emulation/scripts/deploy_underlay.sh abilene --no-cli --load-response
```

Lệnh deploy tự chạy static validation, preflight, OSPF convergence,
reachability, packet forwarding, D-ITG và bài tải 80/100/110%. Chỉ coi
checkpoint đạt khi xuất hiện `UNDERLAY READY`.

## Tài liệu

- [Phương pháp và cơ sở khoa học](docs/phuong_phap_trien_khai_zt_sr_sdwan_containernet.md)
- [Hướng dẫn packet-level emulation](emulation/README.md)
- [Chi tiết routed underlay](emulation/underlay/README.md)
