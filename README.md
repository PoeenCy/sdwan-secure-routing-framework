# Mô phỏng định tuyến bảo mật SD-WAN với Zero Trust và Segment Routing

Dự án này là một khung mô phỏng và kiểm chứng định tuyến bảo mật trong SD-WAN. Hệ thống kết hợp **Zero Trust**, phân đoạn vi mô, các chỉ số trên đồ thị tấn công và các thuật toán định tuyến đường cơ sở để đánh giá tác động của ràng buộc bảo mật lên quyết định chọn đường.

Trạng thái hiện tại: nguyên mẫu nghiên cứu, đã có kiểm thử, benchmark và xuất số liệu. Thành phần `ZT-SR-VI` đang dùng mô hình kiểm chứng tĩnh/value-iteration để đánh giá action masking và reward, chưa phải hệ thống DRL triển khai thực tế.

---

## Kết quả nhanh

![Quy trình xử lý](docs/assets/pipeline_quy_trinh.png)

Flow kiểm chứng chính hiện dùng là `14 -> 5`. Flow này được chọn vì thể hiện rõ `BN` và `AB_G`: path ngắn `14->8->6->5` có `Avg_BN_on_path = 0.75`, còn path thay thế `14->12->0->6->5` có `Avg_BN_on_path = 0.20`.

![Hai tầng đồ thị](docs/assets/two_layer_graph_c_g.png)

![Path trên graph theo kịch bản](docs/assets/scenario_graph_paths.png)

| Kịch bản | Baseline nổi bật | Kết quả chính |
|---|---|---|
| `NORMAL` | `SP/QoS/ZT` | Chọn `14->8->6->5`, delay `38.259 ms`, `Avg_BN = 0.75`. |
| `NORMAL` | `ZT-SR-VI` | Chọn `14->12->0->6->5`, delay `105.300 ms`, `Avg_BN = 0.20`. |
| `BW_CONGESTION` | `QoS/ZT-SR-VI` | Tránh cạnh nghẽn băng thông `14->8`, chuyển sang path thay thế. |
| `TRUST_DEGRADED` | `ZT-Routing` | Né node `6` có trust `0.79 < 0.90`, chọn `14->12->0->7->5`. |
| `TRUST_DEGRADED` | `ZT-SR-VI` | Bị `DENIED/BLOCKED` do trust, zone và action mask không còn path hợp lệ. |
| `STRUCTURE_MITIGATED` | Tất cả baseline | Edge chokepoint `8->6` bị vô hiệu hóa, tất cả chuyển sang path thay thế. |

![Ma trận path theo kịch bản](docs/assets/scenario_path_matrix.png)

Phân tích chi tiết nằm ở [docs/PHAN_TICH_KET_QUA_VA_QUY_TRINH.md](docs/PHAN_TICH_KET_QUA_VA_QUY_TRINH.md). Bảng số liệu cuối cùng nằm ở [zt_sr_sdwan/results/calculations/final_baseline_statistics_validation_flow.csv](zt_sr_sdwan/results/calculations/final_baseline_statistics_validation_flow.csv).

---

## Mục tiêu

- Mô hình hóa topology SD-WAN dưới dạng graph kết nối `C`.
- Sinh attack graph `G` để đánh giá đường tấn công và các chỉ số bảo mật.
- Tính các chỉ số như `MSPL`, `NSP`, `BN`, `AB`, `MOD`, `AOD`, `CMC`.
- Tính trust score từ identity, behavior và context.
- Áp dụng phân đoạn vi mô bằng zone matrix và feasible-edge filtering.
- So sánh các thuật toán đường cơ sở: Shortest Path, QoS Routing, Segmentation Routing, Zero Trust Routing và nguyên mẫu ZT-SR.
- Xuất CSV và hình ảnh để kiểm chứng kết quả đo đạc.

## Cấu trúc thư mục

Các thư mục chính của kho mã nguồn:

```text
SD_WAN_Secure_Routing/
├── zt_sr_sdwan/                 # Mã nguồn mô phỏng chính
│   ├── src/                     # Mô hình graph, chỉ số, trust, routing, phân đoạn vi mô
│   ├── scripts/                 # Script benchmark, kịch bản, trực quan hóa, xuất CSV
│   ├── tests/                   # Bộ kiểm thử Pytest
│   ├── config/                  # Cấu hình YAML
│   ├── data/topologies/         # Topology nhỏ dùng làm fixture công khai
│   └── results/                 # CSV và hình ảnh kết quả đã chọn lọc
├── audit_system/                # Module hỗ trợ audit/đối chiếu thiết kế
├── docs/                        # Tài liệu tổng quan và báo cáo kỹ thuật
├── generate_plots.py            # Tạo lại biểu đồ từ CSV kết quả
├── main.py                      # Điểm vào cho workflow audit
├── .gitignore
└── README.md
```

Các bản thảo riêng, prompt local, dữ liệu thô, `.env`, cache và artifact build được loại khỏi Git bằng `.gitignore`.

---

## Cài đặt và chạy nhanh

```bash
git clone <duong-dan-repo>
cd SD_WAN_Secure_Routing/zt_sr_sdwan
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests
python scripts/run_baselines.py
python scripts/export_calculation_csvs.py
```

Từ thư mục gốc của kho mã nguồn có thể tạo lại biểu đồ và hình giải thích:

```bash
python generate_plots.py
python zt_sr_sdwan/scripts/generate_explanatory_diagrams.py
```

## Kết quả minh chứng

Các file kết quả chính:

- `docs/PHAN_TICH_KET_QUA_VA_QUY_TRINH.md`
- `docs/assets/pipeline_quy_trinh.png`
- `docs/assets/two_layer_graph_c_g.png`
- `docs/assets/scenario_graph_paths.png`
- `docs/assets/scenario_path_matrix.png`
- `zt_sr_sdwan/results/calculations/final_baseline_statistics_validation_flow.csv`
- `zt_sr_sdwan/results/calculations/baseline_comparison_by_state.csv`
- `zt_sr_sdwan/results/calculations/robustness_bn_pair_contributions_by_state.csv`
- `zt_sr_sdwan/results/visualizations/chart_delay.png`
- `zt_sr_sdwan/results/visualizations/chart_bandwidth.png`
- `zt_sr_sdwan/results/visualizations/chart_trust.png`
- `zt_sr_sdwan/results/graph_c_visualization.png`
- `zt_sr_sdwan/results/graph_g_visualization.png`
- `docs/reports/bao_cao_giai_doan_chi_so_va_routing_tinh.md`

![So sánh delay](zt_sr_sdwan/results/visualizations/chart_delay.png)

---

## Tài liệu

Bắt đầu từ [docs/README.md](docs/README.md). Tài liệu phân tích chính là [docs/PHAN_TICH_KET_QUA_VA_QUY_TRINH.md](docs/PHAN_TICH_KET_QUA_VA_QUY_TRINH.md); phần tổng quan ngắn nằm ở [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md).

## Ghi chú phạm vi

Dự án này nên được hiểu là khung mô phỏng và kiểm chứng. Nó chưa phải SD-WAN controller triển khai thực tế và chưa khẳng định kết quả DRL ở mức triển khai thực tế. Các kết quả hiện tại tập trung vào tính đúng của chuỗi xử lý chỉ số, lọc theo trust, mặt nạ hành động và so sánh đường cơ sở.
