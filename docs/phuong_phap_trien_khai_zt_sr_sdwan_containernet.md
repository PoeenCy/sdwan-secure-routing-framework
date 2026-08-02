# Phương pháp triển khai hạ tầng thử nghiệm ZT-SR-SDWAN trên Containernet

## 1. Mục tiêu và phạm vi

Tài liệu này mô tả phương pháp xây dựng một hạ tầng thử nghiệm cho **Zero Trust–aware Secure Routing trong SD-WAN**. Mục tiêu là tạo ra một môi trường:

- có nhiều node underlay và nhiều site overlay;
- chạy traffic TCP/UDP và phiên tấn công thật bằng container;
- cho phép bộ điều khiển SDN thay đổi đường đi hoặc chặn flow;
- tạo congestion, queueing delay và congestion loss ở mức packet;
- bảo đảm mỗi topology, tham số link, traffic profile, queue model và kịch bản tấn công đều có nguồn hoặc phương pháp công bố rõ ràng;
- tái lập được bằng mã nguồn, file cấu hình, phiên bản phần mềm và random seed.

Đây là **packet-level network emulation trên Linux**, không phải mạng SD-WAN sản xuất. Kết quả được dùng để chứng minh tính đúng đắn, khả năng phản ứng và hiệu quả tương đối của framework trong một môi trường có kiểm soát.

---

## 2. Kiến trúc tổng thể

```text
                           CONTROL PLANE
                  +-----------------------------+
                  | OS-Ken Controller           |
                  | Python + NetworkX           |
                  +-------------+---------------+
                                |
                    OpenFlow chỉ tới các CPE
                                |
        =================================================
                         SD-WAN OVERLAY
        CPE-HQ ==== CPE-BR1 ==== CPE-BR2 ==== CPE-DC
           \\          |             |          //
             CPE-DMZ ================== CPE-CLOUD
        =================================================
                 VXLAN/GRE tunnels qua underlay
                                |
        -------------------------------------------------
                         IP WAN UNDERLAY
             Linux Router / FRRouting / OSPF
            topology công bố + link parameters
        -------------------------------------------------
                                |
             LAN segments và Docker applications
          HR | IT/Kali | DMZ/Vulhub | FIN | Cloud
                                |
             Suricata + Telemetry + System Monitor
```

Hạ tầng được chia thành bốn lớp:

1. **Application/LAN plane:** các endpoint và ứng dụng Docker.
2. **WAN underlay:** mạng IP độc lập gồm các Linux router.
3. **SD-WAN overlay:** các CPE Open vSwitch và tunnel VXLAN/GRE.
4. **Control, telemetry và security plane:** OS-Ken, Suricata và bộ thu telemetry.

Bộ điều khiển **không điều khiển router underlay**. Nó chỉ điều khiển CPE ở biên overlay.

---

## 3. Nền tảng phần mềm

| Thành phần | Vai trò |
|---|---|
| Ubuntu Linux | Hệ điều hành host chạy thí nghiệm |
| Containernet | Tạo topology Mininet và đưa Docker container vào mạng |
| Docker | Chạy endpoint, ứng dụng, router, IDS và traffic generator |
| Open vSwitch | Làm SD-WAN CPE, LAN switch và điểm thực thi OpenFlow |
| FRRouting | Chạy static routing hoặc OSPF trên router underlay |
| Linux `tc` | Giới hạn capacity, tạo propagation delay và cấu hình queue |
| OS-Ken | Bộ điều khiển OpenFlow; được ưu tiên thay cho Ryu cũ |
| NetworkX | Biểu diễn graph và tính đường có trọng số không âm |
| D-ITG / iperf3 | Sinh traffic nền và traffic ứng dụng |
| Suricata | Phân tích traffic mirror và xuất EVE JSON |
| Prometheus/CSV/InfluxDB | Lưu telemetry, log và kết quả thí nghiệm |
| psutil/cAdvisor | Theo dõi tài nguyên của host và container |

Containernet được chọn vì nó hỗ trợ Docker host, dynamic topology, giới hạn CPU/RAM và traffic-control link với bandwidth, delay, loss và jitter [1].

---

## 4. Phương pháp xây dựng mạng underlay

### 4.1. Nguồn topology

Topology underlay triển khai chính là **SNDlib Abilene** [7]. Bundle đầu vào
được ghim bằng SHA-256 và gồm:

- topology XML có 12 node và 15 physical link;
- capacity trong `preInstalledModule.capacity`, unit `MBITPERSEC`;
- readme provenance của Abilene;
- archive traffic matrix động và một epoch 5 phút được chọn cố định.

Parser đọc trực tiếp XML SNDlib và dừng nếu metadata bắt buộc không hợp lệ.
Mỗi link trong instance được triển khai như một physical link bidirectional vì
data plane IP cần giao tiếp hai chiều; quyết định này được ghi trong manifest.

SNDlib ghi rõ tọa độ chủ yếu phục vụ visualization. Vì vậy tọa độ chỉ là đầu
vào cho mô hình delay công bố ở mục 4.4, không được gọi là tuyến cáp thực tế.

### 4.2. Biểu diễn router underlay

Mỗi node topology được triển khai thành một Linux router/container:

```text
Router container
├── Linux network namespace
├── IP forwarding
├── FRRouting
└── một interface cho mỗi link kề
```

Underlay sử dụng:

- static routing trong giai đoạn kiểm thử ban đầu;
- OSPF trong thí nghiệm chính;
- ECMP chỉ bật trong profile riêng nếu cần đánh giá multipath underlay.

Không dùng `OVSSwitch(failMode="standalone")` để thay router WAN, vì chế độ đó chủ yếu tạo switch L2 tự học MAC và không đại diện cho một mạng IP routed.

### 4.3. Capacity và phép scale

Capacity được đọc từ metadata của từng edge nếu dataset cung cấp giá trị rõ ràng. Không mặc định mọi topology đều có capacity đầy đủ.

Do giới hạn máy thử nghiệm, capacity có thể được scale theo một hệ số chung:

\[
C'_{ij} = \frac{C_{ij}}{k}
\]

Trong đó:

- \(C_{ij}\) là capacity trong dataset;
- \(C'_{ij}\) là capacity cấu hình vào Containernet;
- \(k\) là hệ số scale được công bố trong cấu hình thí nghiệm.

Nếu traffic matrix cũng được scale, phải dùng cùng hệ số:

\[
D'_{st}(t) = \frac{D_{st}(t)}{k}
\]

Mục tiêu là giữ nguyên tỷ lệ tải tương đối:

\[
\frac{D'_{st}(t)}{C'_{ij}}
\]

Không được giảm capacity nhưng giữ nguyên traffic demand rồi tuyên bố rằng workload vẫn đại diện cho dataset gốc.

### 4.4. Propagation delay

Nếu topology không cung cấp delay đo trực tiếp, delay được ghi rõ là **estimated propagation delay**, không phải delay thực đo.

Quy trình:

1. đọc latitude/longitude của hai đầu link;
2. tính khoảng cách geodesic bằng công thức Haversine;
3. áp dụng hệ số kéo dài tuyến cáp `stretch factor`;
4. chia cho tốc độ truyền trong sợi quang.

\[
d^{prop}_{ij}
=
\frac{\alpha \times d^{geo}_{ij}}
{204{,}000\ \text{km/s}}
\]

Trong đó:

- \(d^{geo}_{ij}\): khoảng cách geodesic;
- \(\alpha\): stretch factor;
- \(204{,}000\ \text{km/s}\): tốc độ gần đúng của ánh sáng trong sợi quang.

Một nghiên cứu về latency hạ tầng quang sử dụng quy tắc kinh nghiệm `2.1 × khoảng cách đường chim bay / tốc độ ánh sáng trong sợi quang` để ước lượng latency Internet [2]. Vì vậy profile mặc định có thể dùng \(\alpha=2.1\), đồng thời thực hiện sensitivity analysis với các giá trị khác.

Cần phân biệt:

```text
Configured propagation delay = kết quả mô hình địa lý
Queueing delay               = phát sinh động khi queue có tải
Processing/scheduling delay  = overhead của host emulation
End-to-end delay             = tổng các thành phần trên
```

#### 4.4.1. Ranh giới giữa cấu hình tĩnh và đo lường động

Haversine chỉ được thực thi khi dựng plan để tạo
$d^{cfg}_{prop}$, sau đó giá trị này được nạp vào TCLink/NetEm. Nó không được
dùng lại như một mẫu dữ liệu đo:

\[
d^{cfg}_{prop,e}
= \frac{\alpha d^{geo}_e}{v_f}\times 10^3\ \text{ms}
\quad\longrightarrow\quad
\texttt{TCLink(delay=...)}
\]

Sau `net.start()`, kết quả phải đến từ packet và counter thật:

\[
d^{meas}_{D\text{-}ITG}=t_{recv}-t_{send},
\qquad
RTT^{meas}_{probe}=t_{reply}-t_{send},
\]

\[
loss^{meas}
= \frac{N_{sent}-N_{received}}{N_{sent}},
\qquad
\Delta drop_{qdisc}=drop_{after}-drop_{before}.
\]

Artifact phải được tách vật lý thành hai thư mục:

```text
configuration/  # capacity/delay/queue được nạp; không dùng vẽ kết quả
measurements/   # D-ITG, ping/probe, tcpdump và tc counter quan sát khi chạy
```

Dashboard chỉ đọc file có `artifact_class=measurement` và
`plot_eligible=true`. Nếu một biểu đồ delay đọc trực tiếp `delay_ms` từ
underlay plan thì biểu đồ đó chỉ là visualization của cấu hình, không phải
kết quả thực nghiệm và phải bị từ chối trong pipeline kết quả.

### 4.5. Queue và congestion loss

Trên mỗi egress bottleneck:

- HTB hoặc TBF áp capacity;
- NetEm áp propagation delay;
- CoDel hoặc FQ-CoDel quản lý queue.

CoDel được định nghĩa trong RFC 8289 và sử dụng packet sojourn time để phát hiện persistent queueing delay [3]. Nó không chờ buffer đầy mới hoạt động.

Hai queue profile nên được đánh giá:

1. **DropTail/pfifo** làm baseline.
2. **CoDel hoặc FQ-CoDel** làm AQM profile.

Loss cần được phân loại:

- **Congestion drop:** do queue hoặc AQM;
- **Configured random loss:** chỉ dùng nếu có nguồn hoặc kịch bản riêng;
- **Host/emulator drop:** do CPU, backlog hoặc giới hạn tài nguyên.

Không được gọi CoDel drop là physical link loss.

---

## 5. Phương pháp xây dựng SD-WAN overlay

### 5.1. Quy mô overlay

Overlay chính sử dụng khoảng **6 CPE/site**:

| Site | Vai trò |
|---|---|
| CPE-HQ | Trung tâm quản trị hoặc headquarters |
| CPE-BR-HR | Chi nhánh HR |
| CPE-BR-IT | Chi nhánh IT và endpoint quản trị |
| CPE-DC | Data center/FIN |
| CPE-DMZ | Dịch vụ công khai hoặc Vulhub |
| CPE-CLOUD | Cloud/remote service |

Mỗi CPE được ánh xạ cố định vào một PoP underlay khác nhau. File cấu hình phải lưu rõ:

```yaml
cpe_hq: underlay_node_X
cpe_br_hr: underlay_node_Y
cpe_br_it: underlay_node_Z
...
```

Không thay đổi ánh xạ giữa các baseline trong cùng một experiment set.

### 5.2. Topology overlay

Ba profile overlay được sử dụng:

- **Hub-and-spoke:** dùng làm baseline đơn giản.
- **Partial mesh:** profile chính, cân bằng số tunnel và khả năng có đường thay thế.
- **Full mesh:** dùng để kiểm tra scalability với số tunnel lớn.

MEF mô tả SD-WAN là một overlay service có SD-WAN Edge, application flow, policy và một hoặc nhiều underlay connectivity services [4]. Việc tách CPE overlay khỏi underlay routed network tuân theo cách phân lớp này.

### 5.3. Tunnel

Tunnel được tạo sẵn trên CPE bằng VXLAN hoặc GRE:

```text
CPE-A tunnel port
    local_ip  = underlay endpoint của CPE-A
    remote_ip = underlay endpoint của CPE-B
```

Open vSwitch hỗ trợ tunnel port và yêu cầu transport network có IP reachability giữa các endpoint [5].

Bộ điều khiển không tạo tunnel cho từng packet. Nó cài OpenFlow rule để:

```text
flow → output:tunnel_A
flow → output:tunnel_B
flow → drop
```

Mỗi đường thay thế phải có endpoint hoặc routing underlay khác biệt đủ để packet thực sự đi qua các path khác nhau.

### 5.4. Segment mapping

Mỗi endpoint được gắn segment bằng một tập định danh cố định:

```text
VLAN/VNI + access port + IP/MAC → HR / IT / FIN / DMZ / CLOUD
```

Micro-segmentation policy được lưu thành policy matrix có phiên bản. Ví dụ:

| Source | Destination | Service | Default |
|---|---|---|---|
| HR | FIN | HTTPS | Allow |
| HR | FIN | Database port | Deny |
| IT-Admin | DMZ | SSH | Allow có điều kiện |
| DMZ | FIN | Any | Deny |
| Internet/Untrusted | Internal | Any | Deny |

NIST SP 800-207 nhấn mạnh không có implicit trust và mọi truy cập tài nguyên phải được đánh giá, xác thực và cấp quyền theo policy [6].

---

## 6. Traffic workload

### 6.1. Hai loại workload

Thí nghiệm sử dụng hai lớp traffic:

1. **Network-wide demand:** tạo tải cho toàn topology.
2. **Application flows:** tạo hành vi HR, FIN, web, DB hoặc VoIP.

Hai lớp này không được trộn lẫn về ý nghĩa.

### 6.2. Traffic matrix có nguồn

SNDlib cung cấp cho Abilene 48.096 traffic matrix với độ phân giải 5 phút
trong sáu tháng [7]. Deployment ghim epoch
`demandMatrix-abilene-zhang-5min-20040301-0010.xml`: đây là member đầu tiên
theo thời gian có trong archive, không phải một matrix được chọn ngẫu nhiên để
tạo kết quả đẹp.

Capacity và demand đều chia cho cùng hệ số 100. Do đó tỷ lệ demand/capacity
được bảo toàn trong phạm vi sai số và overhead emulation. Manifest lưu URL,
archive member, timestamp, unit và checksum của topology, readme, archive và
matrix đã giải nén.

### 6.3. Hiện thực traffic bằng D-ITG

Ở checkpoint underlay, demand lớn nhất trong profile được chọn bằng policy cố
định `maximum_scaled_demand_in_selected_profile` và chuyển thành một probe
D-ITG:

```text
OD demand s→t
→ source container tại site s
→ receiver container tại site t
→ rate và duration theo traffic epoch
```

D-ITG hỗ trợ nhiều flow đồng thời, TCP/UDP, nhiều phân phối inter-departure và packet size, cùng log delay, jitter, throughput và loss [8].

Probe này chứng minh một demand từ dataset đã thành gói thật và đi xuyên routed
underlay. Nó không được gọi là replay toàn bộ traffic matrix. Việc phát đồng
thời toàn bộ OD demand thuộc checkpoint workload sau khi gắn các site/CPE.

Các traffic profile Pareto, Poisson hoặc exponential chỉ được dùng khi:

- cú pháp D-ITG đúng với manual;
- khai báo rõ phân phối áp cho inter-departure hay packet size;
- có đủ shape, scale, mean, protocol, duration và seed.

Không gọi một flow là “web traffic thực tế” chỉ vì dùng Pareto. Phát biểu đúng hơn là:

> Flow được cấu hình để tái tạo đặc tính heavy-tailed hoặc stochastic đã được mô tả trong nghiên cứu trước.

### 6.4. Background traffic và attack traffic

Background traffic phải chạy giữa các container generator/receiver riêng. Không sử dụng chính Vulhub làm `iperf` sink, vì như vậy tải ứng dụng, tải congestion và tải tấn công bị trộn.

```text
background-src → background-sink
Kali          → Vulhub
HR/FIN flows  → application receivers
```

---

## 7. Kịch bản tấn công và giám sát

### 7.1. Victim

Victim được triển khai từ một scenario cụ thể của Vulhub. Ví dụ:

```text
repository: vulhub/vulhub
scenario: tomcat/CVE-2017-12615
Tomcat: 8.5.19
deployment: docker compose build && docker compose up
```

Vulhub mô tả CVE-2017-12615 là tình huống ghi file tùy ý thông qua HTTP PUT trong scenario Tomcat 8.5.19 [9].

Để bảo đảm tái lập:

- pin commit của Vulhub;
- lưu Dockerfile và Compose file;
- ghi image digest sau khi build;
- ghi checksum của exploit script.

### 7.2. Attacker

Kali Linux chạy trong Docker container và thực hiện request/exploit trực tiếp qua mạng emulation. Không replay PCAP làm nguồn tấn công chính.

Mỗi attack run phải lưu:

```text
attack start/end timestamp
source/destination
CVE/scenario
exploit command hoặc script version
HTTP response/result
attack success/failure
```

### 7.3. Suricata

CPE tạo OVS Mirror/SPAN đưa bản sao traffic tới Suricata. Open vSwitch có hỗ trợ mirror traffic tới một port hoặc GRE tunnel [10].

Suricata:

- dùng ET Open hoặc ruleset có phiên bản;
- bật EVE JSON;
- lưu alert, flow và HTTP metadata;
- chuyển alert đến controller hoặc log consumer.

EVE JSON có thể xuất alert, anomaly, metadata và protocol records dưới dạng JSON [11].

Không được giả định ET Open chắc chắn có rule cho mọi CVE. Trước thí nghiệm chính cần xác minh:

1. payload tới được victim;
2. sensor nhận đúng traffic;
3. Suricata sinh alert;
4. SID/signature đúng với hành vi cần phát hiện;
5. nếu không có rule phù hợp, custom rule phải được công bố như một artifact của nghiên cứu.

---

## 8. Telemetry mạng

### 8.1. Nguồn telemetry

| Nguồn | Dữ liệu |
|---|---|
| OpenFlow PortStats | packet/byte/error/drop counters |
| OpenFlow FlowStats | counters theo flow |
| `tc -s qdisc` | queue backlog, overlimit, drop, ECN |
| Active probes | RTT, reachability, loss |
| D-ITG logs | packet-level delay, jitter, throughput, loss |
| Suricata EVE | alert và flow metadata |
| Host monitoring | CPU, RAM, swap, softirq, throttling |

OFPPortStats không cung cấp trực tiếp available bandwidth. Throughput được tính từ chênh lệch counter:

\[
Throughput(t)
=
\frac{8(B_{t_2}-B_{t_1})}
{t_2-t_1}
\]

Available bandwidth cần active probing hoặc estimation riêng và phải được gọi đúng là giá trị ước lượng.

### 8.2. Chu kỳ thu thập

Mỗi thí nghiệm phải khóa:

- polling interval;
- active probe interval;
- controller decision interval;
- warm-up period;
- experiment duration;
- timestamp format.

Nếu đo one-way delay giữa các máy vật lý khác nhau, cần đồng bộ clock. Khi mọi namespace chạy trên cùng host, chúng dùng chung clock kernel nhưng vẫn phải thống nhất timestamp.

---

## 9. Control plane

### 9.1. Bộ điều khiển

Ryu hiện không còn được duy trì và repository chính thức khuyến nghị OS-Ken như một lựa chọn được duy trì [12]. Vì vậy:

- **OS-Ken** được ưu tiên cho triển khai chính;
- Ryu chỉ dùng nếu cần tương thích với code cũ và phải pin phiên bản.

Controller chỉ kết nối OpenFlow tới các CPE Open vSwitch. Router underlay không đăng ký với controller.

### 9.2. Graph và path computation

NetworkX biểu diễn:

- CPE overlay nodes;
- available tunnel/virtual links;
- telemetry và security attributes.

Dijkstra trong NetworkX yêu cầu edge weight không âm [13]. Vì vậy mọi cost function đưa vào Dijkstra phải được chuẩn hóa để không tạo trọng số âm.

Kết quả tính toán được dịch thành:

- `FlowMod` để allow/drop/chọn tunnel;
- `GroupMod` cho fast-failover hoặc multipath profile;
- timeout/cookie để quản lý vòng đời rule.

---

## 10. Quy trình chạy thí nghiệm

### Giai đoạn 1 — Kiểm tra hạ tầng

1. dựng underlay;
2. xác minh OSPF/static route hội tụ;
3. ping giữa các underlay endpoint;
4. tạo tunnel;
5. xác minh packet đi qua đúng router bằng `tcpdump`;
6. xác minh không có đường tắt qua management network.

### Giai đoạn 2 — Kiểm tra telemetry

1. sinh một flow nhỏ;
2. kiểm tra OVS counters;
3. kiểm tra `tc -s qdisc`;
4. kiểm tra probe delay/loss;
5. kiểm tra log lưu đúng timestamp.

### Giai đoạn 3 — Kiểm tra security sensor

1. mirror traffic tới Suricata;
2. chạy benign request;
3. chạy exploit;
4. xác minh SID và EVE JSON;
5. xác minh controller nhận event.

### Giai đoạn 4 — Thí nghiệm mạng

1. warm-up;
2. chạy traffic matrix;
3. tăng tải theo profile;
4. ghi congestion/queue state;
5. cho framework chọn tunnel hoặc reroute;
6. ghi thời gian phản ứng và kết quả.

### Giai đoạn 5 — Thí nghiệm security

1. chạy benign workload ổn định;
2. bắt đầu attack tại timestamp cố định;
3. Suricata phát alert;
4. controller cập nhật policy/routing;
5. CPE reroute, isolate hoặc drop;
6. xác minh phiên tấn công bị gián đoạn hoặc bị giới hạn.

---

## 11. Thiết kế đánh giá

Các baseline nên chạy trên cùng topology, workload và seed:

1. shortest path;
2. QoS-only routing;
3. segmentation-only;
4. trust-only;
5. link-risk-only;
6. framework đầy đủ.

Các metric chính:

- end-to-end delay;
- packet loss;
- throughput;
- maximum link utilization;
- routing convergence/reroute time;
- attack containment time;
- policy violation count;
- safe path availability;
- control-plane overhead;
- CPU/RAM của host và controller.

Mỗi scenario cần:

- nhiều lần lặp;
- fixed seed list;
- median, mean và confidence interval;
- warm-up giống nhau;
- reset topology và rules giữa các run.

---

## 12. Kiểm soát giới hạn phần cứng

Containernet chia sẻ kernel, CPU và memory của host. Vì vậy host saturation có thể làm sai delay và loss.

Không sử dụng một ngưỡng tùy ý như `CPU < 85%` để kết luận run hợp lệ. Cần chạy calibration:

```text
5 routers
→ 10 routers
→ 15 routers
→ toàn topology
```

Ở mỗi mức, đo:

- per-core CPU;
- softirq;
- load average;
- RAM/swap;
- Docker throttled time;
- host interface drops;
- OVS datapath drops;
- scheduling jitter;
- throughput của một flow chuẩn.

Ngưỡng hợp lệ được chọn tại điểm trước khi delay/throughput chuẩn bắt đầu sai lệch có hệ thống.

Nếu host bị saturation, run phải bị loại hoặc giảm traffic/topology scale. Không được lấy kết quả nhỏ rồi nhân tuyến tính lên topology lớn.

---

## 13. Bảng provenance

| Thành phần | Nguồn/phương pháp | Cách áp dụng | Không được tuyên bố |
|---|---|---|---|
| Underlay topology | SNDlib Abilene XML | 12 router/15 physical link | Bản đồ router/cáp sản xuất hiện tại |
| Capacity | `preInstalledModule.capacity` | Chia 100, HTB trên mỗi egress | Không gọi throughput đo thực của Abilene hiện tại |
| Propagation delay | Haversine + fiber model | NetEm delay | Không gọi delay đo thực |
| Traffic demand | SNDlib matrix `20040301-0010` | Chia 100; D-ITG probe | Không gọi một probe là replay toàn matrix |
| Queue | Linux tc + CoDel RFC 8289 | Egress sau HTB/NetEm | Không gọi AQM drop là physical loss |
| Overlay | MEF-aligned edge/tunnel abstraction | OVS VXLAN/GRE | Không gọi fabric OVS phẳng là SD-WAN |
| Zero Trust | NIST SP 800-207 principles | policy/micro-segmentation | Không giả định segment/IP đồng nghĩa identity hoàn chỉnh |
| Attack | Vulhub scenario + pinned artifact | Live session từ Kali | Không dùng PCAP replay làm bằng chứng chính |
| Detection | Suricata + verified SID | EVE JSON | Không giả định ET Open luôn phát hiện |
| Controller | OS-Ken/OpenFlow | Chỉ điều khiển CPE | Không điều khiển dumb underlay |
| Path solver | NetworkX | Non-negative weighted graph | Không dùng Dijkstra với cost âm |
| Resource validity | Calibration + monitoring | Loại run bị saturation | Không dùng ngưỡng CPU tùy ý |

---

## 14. Những tuyên bố khoa học có thể sử dụng

Có thể viết:

> Framework được đánh giá trong một môi trường packet-level emulation tái lập được, trong đó topology và capacity được lấy từ dataset công bố; propagation delay được suy ra bằng mô hình địa lý–sợi quang đã được công bố; traffic demand được lấy từ traffic matrix hoặc gravity model có seed cố định; queueing delay và congestion drop phát sinh động từ Linux traffic control và AQM.

Không nên viết:

> Môi trường tái tạo chính xác mạng Abilene lịch sử hoặc một mạng SD-WAN sản
> xuất thực tế.

Phát biểu phù hợp hơn:

> Môi trường duy trì cấu trúc topology, tỷ lệ capacity/traffic và cơ chế packet forwarding đủ để so sánh công bằng các phương pháp routing và security enforcement trong cùng điều kiện.

---

## 15. Artifact cần công bố

Repository thí nghiệm nên chứa:

```text
topology/
  abilene.xml
  demandMatrix-abilene-zhang-5min-20040301-0010.xml
  parsed_topology.json
  cpe_mapping.yaml

configs/
  link_profiles.yaml
  queue_profiles.yaml
  overlay_profiles.yaml
  segment_policy.yaml

traffic/
  traffic_matrices/
  ditg_scripts/
  seeds.txt

security/
  vulhub_commit.txt
  suricata.yaml
  rules/
  exploit_scripts/

controller/
  osken_app/
  networkx_graph/

experiments/
  run_scenario.py
  monitor.py
  reset.sh

results/
  raw_logs/
  processed_metrics/
  figures/
```

Mỗi run cần lưu một manifest gồm version, commit, image digest, topology, profile, seed, thời gian chạy và trạng thái tài nguyên host.

---

## 16. Trạng thái triển khai underlay

Checkpoint underlay đã được chạy trên Parrot OS với image
`zt-sdwan-router:local` digest
`sha256:b4f37fe3439a5b7ea11a008df3dc39cf039c567d452650d6f71daa04a7fcc56b`.

Kết quả full profile:

- 12 router container và 15 veth link;
- FRR/OSPF hội tụ, 132/132 phép ping loopback thành công;
- 30 egress interface có HTB→NetEm→CoDel;
- TCP iperf3 được tcpdump và interface counter xác nhận đi qua 5 hop;
- D-ITG phát demand `WASHng_NYCMng` đã scale 1,53845555 Mbps, nhận 947
  packet với bitrate 1.516,103 Kbit/s và average delay 3,542 ms;
- trên link 24,8 Mbps, tải 80/100/110% lần lượt nhận
  19,808/24,062/24,064 Mbps; loss 0/2,750/9,048%; concurrent RTT
  12,233/29,023/158,696 ms;
- các cờ `below_capacity_preserved`, `capacity_enforced`,
  `congestion_reacted` và `aqm_observed` đều bằng `true`.

Artifact được tách theo profile tại
`emulation/runtime/underlay/mini/` và
`emulation/runtime/underlay/abilene/`. Thư mục runtime không commit vì chứa
output sinh lại được.

Kết luận checkpoint: routed underlay đã sẵn sàng làm transport cho CPE/tunnel.
Overlay, replay đồng thời toàn bộ traffic matrix, Vulhub/Kali, Suricata và
OS-Ken chưa thuộc trạng thái “đã triển khai” của checkpoint này.

---

# Tài liệu tham khảo

1. Containernet Documentation — Docker hosts, dynamic topology, resource limitation và traffic-control links:
   https://containernet.github.io/

2. Bozkurt, I. N. et al., *Dissecting Latency in the Internet's Fiber Infrastructure*, 2018:
   https://arxiv.org/abs/1811.10737

3. RFC 8289 — Controlled Delay Active Queue Management:
   https://www.rfc-editor.org/rfc/rfc8289.html

4. MEF 70.2 — SD-WAN Service Attributes and Service Framework:
   https://www.mplify.net/wp-content/uploads/MEF-70.2.pdf

5. Open vSwitch — Connecting VMs Using Tunnels:
   https://docs.openvswitch.org/en/stable/howto/tunneling/

6. NIST SP 800-207 — Zero Trust Architecture:
   https://doi.org/10.6028/NIST.SP.800-207

7. SNDlib Abilene overview and dynamic traffic matrices:
   https://sndlib.put.poznan.pl/abilene.overview.action

8. D-ITG Manual:
    https://traffic.comics.unina.it/software/ITG/manual/D-ITG-2.8.1-manual.pdf

9. Vulhub — Tomcat CVE-2017-12615 scenario:
    https://github.com/vulhub/vulhub/tree/master/tomcat/CVE-2017-12615

10. Open vSwitch FAQ — Port mirroring:
    https://docs.openvswitch.org/en/stable/faq/configuration/

11. Suricata Documentation — EVE JSON Output:
    https://docs.suricata.io/en/suricata-8.0.6/output/eve/eve-json-output.html

12. Ryu project status and OS-Ken recommendation:
    https://github.com/faucetsdn/ryu
    https://docs.openstack.org/os-ken/latest/

13. NetworkX Dijkstra documentation:
    https://networkx.org/documentation/stable/reference/algorithms/shortest_paths/dijkstra.html
