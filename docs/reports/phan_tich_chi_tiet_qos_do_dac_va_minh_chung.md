# Phân tích chi tiết QoS, đo đạc thuật toán routing, và minh chứng hình vẽ

Ngày đo: 2026-07-05  
Phạm vi: kết quả vừa chạy trong giai đoạn tính toán chỉ số + prototype routing tĩnh `ZT-SR-VI`.  
Mục tiêu: tách rõ từng công thức QoS, từng thuật toán chọn đường, cách lấy số liệu, và bằng chứng để đối chiếu với hình vẽ/bảng kết quả.

Bộ CSV chi tiết đã được xuất tại:

```text
zt_sr_sdwan/results/calculations/
```

Các file chính dùng để đối chiếu:

| File CSV | Dùng để kiểm chứng |
|---|---|
| `qos_edge_metrics_by_state.csv` | Công thức QoS trên từng edge |
| `routing_path_edge_breakdown_by_state.csv` | Cộng dồn delay/QoS/reward theo từng edge của path |
| `routing_path_summary_by_state.csv` | Kết quả path-level của từng baseline |
| `robustness_bn_pair_contributions_by_state.csv` | BN theo từng cặp `r,l`, đúng công thức `NSP_rl(n)/NSP_rl` |
| `bn_ab_controlled_demo.csv` | Ví dụ kiểm soát có hai node trung gian để minh họa BN và `AB_G` khác 0 |
| `bn_ab_validation_summary.csv` | Tóm tắt path validation `14 -> 12 -> 2 -> 4` có `Avg BN on path` và `AB_G` khác 0 |
| `robustness_global_metrics_by_state.csv` | MSPL, NSP, CMPL, CMC, MOD, AOD, `AB_G` |
| `trust_node_scores_and_masks_by_state.csv` | Trust score và node mask |
| `feasible_edges_by_state.csv` | Feasible edge sau active/zone/mask filtering |

## 1. Nguồn số liệu QoS

QoS hiện chưa lấy từ telemetry thật. Code gán synthetic QoS trong:

```text
zt_sr_sdwan/src/models/graph_c.py
GraphC.assign_synthetic_qos(seed=42)
```

Với mỗi edge trong topology C:

```python
delay_ms = rng.uniform(5, 40)
bandwidth_mbps = rng.choice([50, 100, 150, 200, 300, 500])
loss_rate = rng.uniform(0.0001, 0.005)
```

Do seed cố định `42`, cùng topology sẽ sinh cùng bộ QoS. Vì vậy số liệu benchmark có thể lặp lại được.

Các đại lượng QoS đang đo:

| Đại lượng | Cách lấy |
|---|---|
| Delay của edge | `C[u][v]["delay_ms"]` |
| Bandwidth của edge | `C[u][v]["bandwidth_mbps"]` |
| Delay của path | tổng delay các edge trên path |
| Bandwidth của path | min bandwidth trên path, tức bottleneck bandwidth |
| QoS composite weight | `delay_ms + 1000.0 / bandwidth_mbps` |

Lưu ý quan trọng: cột `Bandwidth (Mbps)` trong `benchmark_results.csv` hiện là bottleneck bandwidth của path, không phải `Max Link Util %`. Code hiện chưa tính utilization theo traffic demand/capacity.

## 2. Công thức đo path-level

Với path:

```text
p = [v0, v1, ..., vk]
```

### 2.1 Tổng delay

```text
Delay(p) = sum delay_ms(vi, vi+1)
```

Ví dụ path normal:

```text
14 -> 12 -> 0 -> 7
Delay = delay(14,12) + delay(12,0) + delay(0,7)
      = 32.3255 + 33.1668 + 39.1468
      = 104.6391 ms
```

### 2.2 Bottleneck bandwidth

```text
Bandwidth(p) = min bandwidth_mbps(vi, vi+1)
```

Ví dụ:

```text
14 -> 12 -> 0 -> 7
Bandwidth = min(200, 500, 300) = 200 Mbps
```

### 2.3 QoS composite cost

Dùng riêng cho QoS-Routing:

```text
QoSWeight(e) = delay_ms(e) + 1000 / bandwidth_mbps(e)
QoSWeight(p) = sum QoSWeight(e)
```

Ví dụ:

```text
QoSWeight(14,12) = 32.3255 + 1000/200 = 37.3255
QoSWeight(12,0)  = 33.1668 + 1000/500 = 35.1668
QoSWeight(0,7)   = 39.1468 + 1000/300 = 42.4801
QoSWeight(path)  = 114.9724
```

### 2.4 Avg BN on path và AB_G

Trong benchmark, cột `Avg BN on path` là chỉ số phụ để nhìn nhanh một routing path trên graph C có đi qua các node đang có BN cao trên attack graph G hay không:

```text
AvgBN_on_path(p) = (1 / |p|) * sum_{v in p} BN(v)
```

Chỉ số này được tính trong `scripts/run_baselines.py` bằng cách lấy `bridge.bn_scores[node]` cho từng node trên path rồi chia cho số node của path. Nó không phải công thức `AB_G` của bài báo.

BN chuẩn theo Basta et al. được tính trên từng cặp root-target của graph G:

```text
BN(n) = sum_{r in R_G, l in L_G, r != l} NSP_rl(n) / NSP_rl
```

Trong đó `NSP_rl` là số shortest attack paths từ root cụ thể `r` đến target cụ thể `l`; `NSP_rl(n)` là số shortest attack paths của cặp đó đi qua `n` như intermediate node. Endpoint `r` và `l` không được tính.

Average Betweenness của graph G là:

```text
AB_G = (1 / |L_G|) * sum_{l in L_G} BN(l)
```

Vì vậy `AB_G` là network-level metric trên `L_G`, còn `Avg BN on path` chỉ là diagnostic path-level của benchmark routing.

## 3. Từng thuật toán chọn path như thế nào

Flow benchmark đang xét:

```text
source = 14, zone IT
target = 7, zone FIN
```

### 3.1 SP-Routing

Code:

```text
zt_sr_sdwan/src/routing/baselines.py
Baselines.sp_routing()
```

Thuật toán:

1. Tạo graph tạm chỉ chứa edge active `bandwidth_mbps > 0`.
2. Gán weight là `delay_ms`.
3. Chạy:

```python
nx.shortest_path(temp_g, source=s, target=d, weight="delay_ms")
```

Nghĩa là SP-Routing chỉ tối thiểu hóa tổng delay. Nó bỏ qua zone matrix, trust, BN, MOD, CVE.

### 3.2 QoS-Routing

Code:

```text
Baselines.qos_routing()
```

Thuật toán:

1. Tạo graph tạm chỉ chứa edge active.
2. Với mỗi edge:

```python
qos_weight = delay_ms + 1000.0 / bandwidth_mbps
```

3. Chạy Dijkstra theo `qos_weight`.

Nghĩa là QoS-Routing ưu tiên delay thấp và bandwidth cao, nhưng vẫn không xét security.

### 3.3 Seg-Routing

Code:

```text
Baselines.seg_routing()
ZoneMatrix.is_allowed()
```

Thuật toán:

1. Chỉ giữ edge active.
2. Với mỗi edge `(u,v)`, kiểm tra:

```python
zone_matrix.is_allowed(zone(u), zone(v))
```

3. Sau khi lọc zone matrix, chạy Dijkstra theo `delay_ms`.

Seg-Routing xét micro-segmentation nhưng chưa xét trust và chưa xét structural risk.

### 3.4 ZT-Routing

Code:

```text
Baselines.zt_routing()
PDP.get_trust_score()
```

Thuật toán:

1. Tính `theta_path = pdp.get_theta_path(zone_s, zone_d, C)`.
2. Với mỗi edge `(u,v)`, tính:

```text
T(u), T(v)
```

3. Chỉ giữ edge nếu:

```text
T(u) >= theta_path AND T(v) >= theta_path
```

4. Chạy Dijkstra theo `delay_ms`.

ZT-Routing xét trust nhưng không xét zone matrix và không xét structural mask.

### 3.5 ZT-SR-VI

Code:

```text
Baselines.zt_sr_drl()
ActionMask.build_node_masks()
ActionMask.get_feasible_edges()
ZTEnv
ValueIterationAgent
```

Tên hiện tại là `ZT-SR-VI` vì đang dùng Value Iteration, chưa phải DRL thật.

Pipeline:

1. Tính structural mask từ G:

```text
M_struct(v) = BN(v) <= theta_BN AND MOD(v) <= theta_MOD
```

2. Tính trust mask:

```text
M_trust(v) = T(v) >= theta_path
```

3. Kết hợp node mask:

```text
M_t(v) = M_trust(v) AND M_struct(v)
```

4. Lấy feasible edge set:

```text
E_f = {(u,v) | edge active AND zone allowed AND mask(u) AND mask(v)}
```

5. Value Iteration chọn action bằng reward:

```text
R_t = alpha*norm_bw
      - beta*norm_delay
      - gamma*(lambda1*MOD + lambda2*BN)
      + mu*DeltaMSPL
      - nu*NSP_delta
```

Trong benchmark clean-state hiện tại, tất cả node đều trust cao, BN đều 0, nên nhiều baseline có cùng kết quả.

## 4. Trust và mask trong trạng thái NORMAL

Clean-state setup trong benchmark:

```text
I = 1.0
B = 0.95
C = 1.0
```

Trust formula:

```text
T = 0.4*I + 0.3*B + 0.3*C
  = 0.4*1.0 + 0.3*0.95 + 0.3*1.0
  = 0.985
```

Trong NORMAL:

```text
theta_path = 0.9850000000000001
T(14) = T(12) = T(0) = T(7) = 0.985000
```

Feasible graph cho flow `14 -> 7`:

```text
Tổng edge C = 33
E_f = 30
Pruned edge = 3
Allowed node mask = 19/19
Structural false = ['0']
```

Node `0` bị structural false trong raw struct mask vì MOD cao, nhưng được exempt vì là Core backbone. Vì vậy path qua node `0` vẫn hợp lệ.

Ba edge bị pruned trong feasible graph:

| Edge | Zone | Lý do |
|---|---|---|
| 7 -> 5 | FIN -> DMZ | zone matrix block |
| 8 -> 6 | FIN -> DMZ | zone matrix block |
| 13 -> 18 | HR -> IT | zone matrix block |

## 5. Tính toán path trong NORMAL

Tất cả 5 baseline chọn cùng path:

```text
14 -> 12 -> 0 -> 7
```

Chi tiết từng edge:

| Edge | Zone | Delay | Bandwidth | QoS weight | Reward step |
|---|---|---:|---:|---:|---:|
| 14 -> 12 | IT -> HR | 32.3255 | 200.0 | 37.3255 | -0.036977 |
| 12 -> 0 | HR -> Core | 33.1668 | 500.0 | 35.1668 | -0.349500 |
| 0 -> 7 | Core -> FIN | 39.1468 | 300.0 | 42.4801 | -0.227440 |

Tổng:

```text
Delay = 104.6391 ms
QoS weight = 114.9724
Bottleneck bandwidth = 200 Mbps
Reward sum = -0.613917
```

Đối chiếu với benchmark:

```text
Delay (ms) = 104.64
Bandwidth = 200.0
Hops = 3
Min Trust = 0.9850
Avg BN on path = 0.000000
MSPL = 1
NSP = 2
AB_G = 0
CMC = 6
```

Giá trị `Avg BN on path` bằng 0 vì mọi node trong path `14 -> 12 -> 0 -> 7` đang có `BN(v) = 0` trên attack graph G hiện tại. Giá trị `AB_G` cũng bằng 0 vì tất cả privilege/target nodes trong `L_G` đều có BN bằng 0.

### 5.1 Vì sao path này thắng SP/QoS

Các simple path từ `14` đến `7` với cutoff 8:

| Path | Delay | QoS weight | Bottleneck BW | Zone OK | Reward |
|---|---:|---:|---:|---|---:|
| 14-12-0-7 | 104.6391 | 114.9724 | 200.0 | True | -0.613917 |
| 14-8-6-5-2-1-0-7 | 156.9458 | 187.6124 | 150.0 | False | -0.955837 |
| 14-8-6-5-2-0-7 | 126.6185 | 171.9518 | 50.0 | False | -1.089855 |
| 14-8-6-5-4-3-0-7 | 154.7184 | 188.3851 | 150.0 | False | -0.939155 |

Vì path `14-12-0-7` có delay thấp nhất và QoS weight thấp nhất, SP/QoS chọn nó. Vì path này cũng zone OK và trust OK, Seg/ZT/ZT-SR-VI cũng chọn nó.

## 6. Tính toán path trong TRUST_COMPROMISED

Trong state này node `12` bị giảm behavior:

```text
B(12) = 0.3
T(12) = 0.4*1.0 + 0.3*0.3 + 0.3*1.0 = 0.79
```

Các node khác vẫn:

```text
T = 0.985
```

Adaptive threshold:

```text
theta_path = 1.018279733367803
```

Kết quả mask:

```text
Allowed node mask = 0/19
E_f = 0
```

Vì threshold cao hơn tất cả trust score, ZT-Routing và ZT-SR-VI block flow:

```text
ZT-Routing = DENIED/BLOCKED
ZT-SR-VI = DENIED/BLOCKED
```

SP/QoS/Seg vẫn đi path cũ vì không xét trust:

```text
14 -> 12 -> 0 -> 7
Delay = 104.6391 ms
Min Trust = 0.7900
```

Đây là minh chứng phần trust filtering hoạt động: các baseline không trust vẫn route qua node có trust thấp, còn ZT/ZT-SR thì không.

## 7. Tính toán path trong DELAY_SPIKE

Trong state này edge `14 -> 12` bị tăng delay:

```text
delay(14,12): 32.3255 -> 200.0000 ms
```

### 7.1 SP/QoS/ZT chọn path vòng

Path:

```text
14 -> 8 -> 6 -> 5 -> 2 -> 0 -> 7
```

Chi tiết:

| Edge | Zone | Delay | Bandwidth | QoS weight | Reward step |
|---|---|---:|---:|---:|---:|
| 14 -> 8 | IT -> FIN | 9.8929 | 150.0 | 16.5596 | -0.184679 |
| 8 -> 6 | FIN -> DMZ | 17.9661 | 500.0 | 19.9661 | -0.103898 |
| 6 -> 5 | DMZ -> DMZ | 10.4001 | 150.0 | 17.0668 | -0.086200 |
| 5 -> 2 | DMZ -> Core | 36.2592 | 150.0 | 42.9259 | -0.063778 |
| 2 -> 0 | Core -> Core | 12.9534 | 50.0 | 32.9534 | -0.423860 |
| 0 -> 7 | Core -> FIN | 39.1468 | 300.0 | 42.4801 | -0.227440 |

Tổng:

```text
Delay = 126.6185 ms
QoS weight = 171.9518
Bottleneck bandwidth = 50 Mbps
Reward sum = -1.089855
```

SP chọn path này vì tổng delay thấp hơn path trực tiếp bị delay spike.

QoS cũng chọn path này vì tổng QoS weight thấp hơn path bị spike:

```text
171.9518 < 282.6469
```

ZT cũng chọn path này vì ZT chỉ lọc trust, không lọc zone matrix. Tất cả node trust cao nên path vòng được phép với ZT.

### 7.2 Seg/ZT-SR-VI chọn path qua 12

Path:

```text
14 -> 12 -> 0 -> 7
```

Chi tiết:

| Edge | Zone | Delay | Bandwidth | QoS weight | Reward step |
|---|---|---:|---:|---:|---:|
| 14 -> 12 | IT -> HR | 200.0000 | 200.0 | 205.0000 | -0.540000 |
| 12 -> 0 | HR -> Core | 33.1668 | 500.0 | 35.1668 | -0.349500 |
| 0 -> 7 | Core -> FIN | 39.1468 | 300.0 | 42.4801 | -0.227440 |

Tổng:

```text
Delay = 272.3135 ms
QoS weight = 282.6469
Bottleneck bandwidth = 200 Mbps
Reward sum = -1.116941
```

Vì sao Seg không chọn path vòng nhanh hơn?

Path vòng có edge:

```text
8 -> 6 = FIN -> DMZ
```

Zone matrix hiện block FIN -> DMZ. Do đó path vòng không hợp lệ với Seg-Routing và ZT-SR-VI.

Các candidate path trong DELAY_SPIKE:

| Path | Delay | QoS weight | Bottleneck BW | Zone OK | Reward |
|---|---:|---:|---:|---|---:|
| 14-12-0-7 | 272.3135 | 282.6469 | 200.0 | True | -1.116941 |
| 14-8-6-5-2-1-0-7 | 156.9458 | 187.6124 | 150.0 | False | -0.955837 |
| 14-8-6-5-2-0-7 | 126.6185 | 171.9518 | 50.0 | False | -1.089855 |
| 14-8-6-5-4-3-0-7 | 154.7184 | 188.3851 | 150.0 | False | -0.939155 |

Kết luận: DELAY_SPIKE chứng minh rõ trade-off. Path nhanh hơn tồn tại, nhưng vi phạm zone policy. Prototype bảo mật chấp nhận delay cao hơn để giữ policy.

## 8. Tính toán trong STRUCTURE_MITIGATED

Hiện BN toàn G bằng 0, nên không có BN chokepoint thực sự.

Raw structural mask có:

```text
struct_false = ['0']
```

Node `0` là Core nên được exempt trong action mask. Do đó feasible graph vẫn còn path chính:

```text
14 -> 12 -> 0 -> 7
```

Kết quả tất cả baseline quay lại:

```text
Delay = 104.6391 ms
Bandwidth = 200 Mbps
Hops = 3
```

## 9. Minh chứng hình vẽ

Các hình đã được regenerate bằng code hiện tại vào:

```text
zt_sr_sdwan/results/
```

Timestamp sau khi regenerate:

| Hình | LastWriteTime | Minh chứng số phải khớp |
|---|---|---|
| `graph_c_visualization.png` | 2026-07-05 00:44:33 | C có 19 node, 33 edge, zone labels Core/DMZ/FIN/HR/IT |
| `graph_g_visualization.png` | 2026-07-05 00:44:34 | G có 19 node, 14 edge, R_G={0,5,6,7,8,9}, L_G={0,1,2,3,4,7,8} |
| `feasible_graph_ef.png` | 2026-07-05 00:43:20 | Flow 14->7, E_f=30, pruned edges={7->5, 8->6, 13->18} |
| `routing_path_visualization.png` | 2026-07-05 00:42:54 | Highlight path 14->12->0->7 |

### 9.1 Graph C figure

Script:

```text
scripts/visualize_c_g.py
```

Nguồn dữ liệu:

```text
OverlayManager -> internetmci.graphml -> GraphC
```

Điều hình phải thể hiện:

```text
Nodes = 19
Edges = 33
Node label = node_id + zone
Edge màu xám = connectivity edge trong C
```

Nếu hình C có số node/edge khác các số trên, hình đó không còn khớp snapshot hiện tại.

### 9.2 Graph G figure

Script:

```text
scripts/visualize_c_g.py
```

Nguồn dữ liệu:

```text
bridge.regenerate_g(C)
GraphG.generate_from_c(C, cve_profiles)
```

Điều hình phải thể hiện:

```text
Nodes = 19
Edges = 14
Root outline = R_G
Target outline = L_G
Edge đỏ = exploitability edge trong G
```

Các edge đỏ phải khớp danh sách G edges:

```text
0->6, 0->7, 0->8, 1->0, 2->0, 3->0,
6->5, 7->5, 8->6,
10->9, 11->9, 12->0, 14->8, 18->0
```

### 9.3 Feasible graph figure

Script:

```text
scripts/visualize_feasible_graph.py
```

Nguồn dữ liệu:

```text
ActionMask.build_node_masks(C, pdp, "14", "7", struct_mask)
ActionMask.get_feasible_edges(C, node_masks, zone_matrix)
```

Ở clean state:

```text
node_masks allowed = 19/19
E_f = 30
blocked/pruned = 3
```

Ba edge pruned:

```text
7 -> 5  (FIN -> DMZ, zone blocked)
8 -> 6  (FIN -> DMZ, zone blocked)
13 -> 18 (HR -> IT, zone blocked)
```

Vì vậy feasible graph phải có 30 edge xanh và 3 edge bị prune.

### 9.4 Routing path figure

Script:

```text
scripts/visualize_routing.py
```

Nguồn dữ liệu:

```text
Baselines.zt_sr_drl("14", "7", C, pdp, zm, bridge, agent)
```

Path được highlight:

```text
14 -> 12 -> 0 -> 7
```

Edge-level proof:

```text
14->12 delay=32.3255 bw=200
12->0  delay=33.1668 bw=500
0->7   delay=39.1468 bw=300
Total delay=104.6391
Bottleneck=200
```

## 10. Kết luận chặt chẽ từ số liệu hiện tại

Kết luận có thể claim:

1. QoS hiện được tính deterministic từ synthetic edge attributes với seed 42.
2. SP-Routing tối ưu delay; QoS-Routing tối ưu `delay + 1000/bw`; Seg-Routing lọc zone rồi tối ưu delay; ZT-Routing lọc trust rồi tối ưu delay; ZT-SR-VI lọc zone/trust/struct rồi chọn theo reward.
3. NORMAL cho thấy khi không có rủi ro/trở ngại, mọi baseline hội tụ về cùng path tốt nhất.
4. TRUST_COMPROMISED cho thấy trust-aware routing block flow còn SP/QoS/Seg vẫn đi qua node trust thấp.
5. DELAY_SPIKE cho thấy trade-off bảo mật: path nhanh hơn tồn tại nhưng vi phạm zone matrix, nên Seg/ZT-SR-VI chọn path hợp lệ chậm hơn.

Kết luận chưa được claim:

1. Chưa có `Max Link Util %` thật vì chưa có demand/capacity utilization model.
2. Chưa chứng minh DRL thật, vì `ZT-SR-VI` hiện là Value Iteration/prototype routing tĩnh.
3. Chưa chứng minh MSPL tăng/BN giảm trong benchmark này, vì G hiện tại có `MSPL=1` và `BN=0` toàn mạng.

Do đó báo cáo/hình vẽ hiện tại nên được dùng như bằng chứng cho pipeline đo đạc và prototype policy filtering, không nên dùng để claim kết quả DRL tối ưu cuối cùng.
