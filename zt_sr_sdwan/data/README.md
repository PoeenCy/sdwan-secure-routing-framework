# Thư mục `data` (Dữ liệu đầu vào)

Chứa các dữ liệu topology và dataset để chạy mô phỏng mạng SD-WAN.

## Cấu trúc bên trong

- **`topologies/`**: Chứa các file cấu trúc mạng dạng đồ thị (`.graphml`). File chính là `internetmci.graphml` gồm 19 nút mô phỏng hạ tầng chuẩn học thuật.
- **`traffic/` / `dataset`**: Chứa các dữ liệu traffic thật (ví dụ từ CAIDA) hoặc dataset mô phỏng mạng `network_traffic_dataset.csv` làm đầu vào cho bài toán.
- **`nvd/`**: Nơi lưu trữ thông tin CVE trích xuất từ cơ sở dữ liệu NVD thực tế, phục vụ cho quá trình đánh giá Context rủi ro bảo mật.

Dữ liệu ở đây là nền tảng để xây dựng mạng và đánh giá thuật toán theo các điều kiện thực tế (thay vì chỉ dùng đồ thị tổng hợp random).
