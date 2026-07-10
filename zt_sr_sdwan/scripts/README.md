# Thư mục `scripts` (Kịch bản thực thi)

Thư mục chứa các script hỗ trợ chạy các kịch bản kiểm thử tĩnh, benchmark, vẽ đồ thị hình ảnh và thu thập dữ liệu tự động.

## Các loại Script chính

1. **Scenarios (`run_scenario_s1.py` -> `s5.py`)**:
   - `S1`: Chạy luồng giao thông bình thường (Normal flow).
   - `S2`: Định tuyến lại khi điểm Trust của nút giảm (Trust drop re-route).
   - `S3`: Thay đổi QoS bất ngờ (Telemetry QoS shift).
   - `S4`: Vi phạm SLA (VoIP).
   - `S5`: Cô lập các nút bị outlier (BN outlier isolation).

2. **Benchmark (`run_baselines.py`)**: 
   Chạy đồng loạt 5 thuật toán cơ sở (SP, QoS, Seg, ZT, ZT-SR-VI) để so sánh các chỉ số độ trễ, Trust, và độ bền vững trên cùng bộ dữ liệu. Kết quả được lưu vào `results/`.

3. **Data Fixture**:
   - `fetch_topology.py`: Tải hoặc tạo lại fixture topology InternetMCI dùng cho mô phỏng.

4. **CSV Export**:
   - `export_calculation_csvs.py`: Xuất các bảng tính toán chi tiết cho QoS, trust, BN/AB, feasible edge và so sánh baseline.
   - `generate_explanatory_diagrams.py`: Sinh lại các sơ đồ giải thích trong `docs/assets/`.

5. **Visualizations**:
   Các script như `visualize_c_g.py`, `visualize_routing.py` dùng để render hình ảnh của đồ thị C, G và trực quan hóa đường đi, xuất file ảnh ra thư mục `results/`.
