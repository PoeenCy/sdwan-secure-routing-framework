# Thư mục `config` (Cấu hình hệ thống)

Thư mục này chứa các file YAML quy định tĩnh các chính sách và ma trận cấu hình cho môi trường SD-WAN.

## Các file cấu hình

- **`zone_matrix.yaml`**: Ma trận định nghĩa quyền kết nối cơ bản giữa các vùng mạng (Zone). Trả lời câu hỏi: Zone A có được phép nói chuyện với Zone B không?
- **`zone_mapping.yaml`**: Ánh xạ các nút (node) trong mạng (ví dụ trong InternetMCI topology) vào các vùng (Core Backbone, DMZ, FIN, HR, IT).
- **`trust_policy.yaml`**: Quy định các tham số tính điểm Trust và các ngưỡng (thresholds) cho Policy Decision Point.
- **`cve_profiles.yaml`**: Chứa hồ sơ lỗ hổng bảo mật (CVE) của các nút. Thông tin này được module `trust/context.py` đọc để đưa vào thành phần tính điểm $C$ (Context).
- **`qos_catalog.yaml`**: Thông số QoS yêu cầu cho các loại dịch vụ (ví dụ: VoIP cần băng thông bao nhiêu, độ trễ tối đa bao nhiêu).

Hệ thống luôn tải các cấu hình này lúc khởi tạo Controller để đảm bảo tính nhất quán (Single Source of Truth cho cấu hình tĩnh).
