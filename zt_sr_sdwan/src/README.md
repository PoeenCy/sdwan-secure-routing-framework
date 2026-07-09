# Thư mục `src` (Mã nguồn cốt lõi)

Thư mục này chứa toàn bộ mã nguồn của hệ thống Zero Trust Secure Routing (ZT-SR) SD-WAN, được tổ chức theo kiến trúc dựa trên thiết kế (Design Lock v1) từ `KI_07_Implementation_Blueprint`.

## Cấu trúc bên trong

- **`models/`**: Chứa các cấu trúc dữ liệu nền tảng như `GraphC` (Connectivity overlay), `GraphG` (Attack graph), `Flow` (thông tin phiên kết nối), và các `events` hệ thống.
- **`topology/`**: Quản lý đồ thị mạng vật lý và thu thập telemetry QoS (`overlay_manager.py`).
- **`microseg/`**: Chứa logic xử lý Vi phân đoạn (Micro-segmentation). Bao gồm ma trận vùng (`zone_matrix.py`) và module C-G Bridge (`bridge_cg.py`) tạo đồ thị tấn công G từ đồ thị kết nối C để tính các chỉ số như Basta, Z-score ($\theta$).
- **`trust/`**: Implement cơ chế Policy Decision Point (PDP) của Zero Trust. Tính toán điểm Trust score bằng weighted sum $T = w_I I + w_B B + w_C C$ từ định danh (Identity), ngữ cảnh (Context), và hành vi (Behavior). Đưa ra quyết định GRANT/DENY.
- **`routing/`**: Xử lý định tuyến với sự kết hợp của nhiều ràng buộc. Gồm Action Masking (`M_t`), tìm đường khả thi (`feasible_paths`), các thuật toán cơ sở (Dijkstra, Seg-Routing) và DRL agent.
- **`orchestrator/`**: Điều phối viên trung tâm (SD-WAN Controller) xử lý pipeline cho từng luồng (flow) và các sự kiện của mạng.
- **`metrics/`**: (Nếu có) Tính toán các chỉ số phơi nhiễm trên đồ thị C và độ vững chãi trên đồ thị G.

Module này ánh xạ trực tiếp đến các quyết định thiết kế cốt lõi (R1-R11) trong quá trình nghiên cứu và được xây dựng để đảm bảo có thể chạy thử nghiệm qua các Phase khác nhau (từ nền tảng không có RL đến hệ thống định tuyến đầy đủ ZT-SR-VI).
