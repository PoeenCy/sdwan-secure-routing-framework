# Tổng quan dự án

## Mô phỏng định tuyến bảo mật SD-WAN với Zero Trust và Segment Routing

Dự án này là một nguyên mẫu nghiên cứu bằng Python để đánh giá quyết định định tuyến có xét yếu tố bảo mật trong SD-WAN. Khung mô phỏng này mô hình hóa graph kết nối, attack graph, lớp đánh giá trust, chính sách phân đoạn vi mô và nhiều thuật toán định tuyến đường cơ sở.

## Thành phần đã triển khai

- Mô hình topology SD-WAN dựa trên graph.
- Sinh attack graph và tính các chỉ số robustness.
- Tính Zero Trust score từ identity, behavior và context.
- Micro-segmentation bằng zone policy matrix và feasible-edge filtering.
- Các thuật toán định tuyến đường cơ sở: shortest path, QoS routing, segmentation-aware routing, trust-aware routing và định tuyến nguyên mẫu ZT-SR.
- Xuất CSV và hình ảnh để tái kiểm chứng kết quả.
- Bộ kiểm thử Pytest cho trust scoring, zone matrix, action mask, reward, attack graph generation và robustness metrics.

## Công nghệ sử dụng

- Python
- NetworkX
- NumPy
- PyYAML
- Pytest
- Pandas / Matplotlib / Seaborn for reporting
- Gymnasium / PyTorch cho môi trường RL và thành phần agent nguyên mẫu

## File kết quả minh chứng

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

## Phạm vi hiện tại

Đây là khung mô phỏng và kiểm chứng, không phải SD-WAN controller triển khai thực tế. Thành phần routing nâng cao hiện dùng để kiểm chứng mặt nạ hành động và hành vi value-iteration/nguyên mẫu; chưa phải hệ thống DRL đã huấn luyện hoàn chỉnh để triển khai thực tế.
