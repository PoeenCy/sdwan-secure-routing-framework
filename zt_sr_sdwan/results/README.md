# Thư mục `results`

Thư mục này giữ các kết quả mô phỏng đã chọn lọc để có thể kiểm chứng lại từ README và tài liệu trong `docs/`.

## File nên đọc trước

- `calculations/final_baseline_statistics_validation_flow.csv`: bảng cuối cùng so sánh các baseline theo flow kiểm chứng `14 -> 5`.
- `calculations/bn_ab_controlled_demo.csv`: bảng tách từng bước đóng góp `BN` theo từng cặp `r -> l`.
- `calculations/qos_edge_metrics_by_state.csv`: số đo QoS của từng edge theo từng state.
- `calculations/trust_node_scores_and_masks_by_state.csv`: trust score và mask của từng node.
- `calculations/feasible_edges_by_state.csv`: edge còn hợp lệ sau zone policy, trust mask và action mask.

## Hình ảnh

- `graph_c_visualization.png`: graph kết nối `C`.
- `graph_g_visualization.png`: graph tấn công `G`.
- `feasible_graph_ef.png`: graph sau khi lọc feasible edge.
- `routing_path_visualization.png`: minh họa path định tuyến.
- `visualizations/chart_delay.png`: so sánh delay theo baseline/state.
- `visualizations/chart_bandwidth.png`: so sánh bottleneck bandwidth.
- `visualizations/chart_trust.png`: so sánh trust thấp nhất trên path.

Các file trong thư mục này là output có thể tái tạo bằng script, không nên chỉnh sửa thủ công.
