# Thư mục `tests` (Kiểm thử hệ thống)

Chứa các Unit Test (sử dụng `pytest`) để đảm bảo các module đơn lẻ hoạt động chính xác theo bản vẽ thiết kế (Blueprint). 

## Các file test

- **`test_config_load.py`**: Kiểm tra việc load các file cấu hình YAML.
- **`test_zone_matrix.py`**: Kiểm tra tính đúng đắn của logic phân vùng, ma trận quy tắc.
- **`test_trust_pdp.py`**: Kiểm tra Policy Decision Point, thuật toán tính điểm tổng hợp dựa vào $I, C, B$.
- **`test_action_mask.py`**: Kiểm tra việc tạo Mask (Che giấu/cắt các đường đi không thỏa mãn điều kiện bảo mật/vùng).
- **`test_feasible_paths.py`**: Kiểm tra hàm lấy danh sách đường đi hợp lệ $P_f$ từ không gian các đường dẫn cho phép.

Mọi thay đổi trong `src/` đều phải đảm bảo vượt qua toàn bộ các test này để đảm bảo Framework chạy ổn định trước khi tích hợp vào môi trường Reinforcement Learning.
