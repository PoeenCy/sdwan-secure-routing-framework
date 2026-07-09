# Khung mô phỏng định tuyến bảo mật ZT-SR cho SD-WAN

Dự án này là mã nguồn chính của khung mô phỏng định tuyến bảo mật cho SD-WAN dựa trên Zero Trust và phân đoạn vi mô. Hệ thống được xây dựng bằng Python và thư viện NetworkX.

Mục tiêu cốt lõi của khung mô phỏng là kết hợp ba lớp:

1. **Lớp định tuyến**: Định tuyến luồng mạng trên kiến trúc SD-WAN.
2. **Lớp phân đoạn (Micro-segmentation)**: Cô lập theo vùng mạng và kiểm soát luồng.
3. **Lớp Zero Trust**: Đánh giá mức độ tin cậy dựa trên định danh, ngữ cảnh bảo mật và hành vi.

Đây là môi trường kiểm thử (Giai đoạn 1 và 2) cho bài toán định tuyến đa mục tiêu, nhằm tích hợp các ràng buộc bảo mật vào việc ra quyết định tìm đường trong mạng SD-WAN.

## Kiến trúc thư mục

Mỗi thư mục con đảm nhiệm một vai trò riêng:

| Thư mục | Chức năng | Liên kết chi tiết |
|---|---|---|
| `config/` | Chứa các file cấu hình YAML định nghĩa ma trận phân vùng, QoS, điểm Trust,... | [config/README.md](config/README.md) |
| `data/` | Chứa topology nhỏ và mô tả dữ liệu; dữ liệu thô hoặc dữ liệu tải về nên để local | [data/README.md](data/README.md) |
| `src/` | Mã nguồn cốt lõi (topology, models, microseg, trust, routing...) | [src/README.md](src/README.md) |
| `scripts/` | Chứa script chạy scenario, benchmark, visualization và export CSV | [scripts/README.md](scripts/README.md) |
| `tests/` | Chứa bộ kiểm thử Pytest để xác minh mô hình | [tests/README.md](tests/README.md) |
| `results/` | Chứa CSV và hình ảnh kết quả đã chọn lọc | [results/README.md](results/README.md) |
| `audit_system/` | Hệ thống đối chiếu mã nguồn với yêu cầu thiết kế | `../audit_system/` |

## Quy trình cài đặt và thực thi

### 1. Cài đặt thư viện phụ thuộc

Cài đặt thư viện Python (yêu cầu `networkx`, `numpy`, `pyyaml`,...):

```bash
pip install -r requirements.txt
```

### 2. Sinh đồ thị mạng

Chạy script dưới đây để tải về và xây dựng đồ thị liên kết InternetMCI (19 node) mô phỏng môi trường mạng diện rộng:

```bash
python scripts/fetch_topology.py
```

### 3. Chạy kiểm thử

Trước khi thực thi các kịch bản, chạy bộ test để đảm bảo Policy Decision Point và thuật toán masking hoạt động đúng đặc tả:

```bash
python -m pytest tests
```

### 4. Chạy các kịch bản mô phỏng

Các script từ `S1` đến `S5` dùng để quan sát phản ứng của hệ thống khi có thay đổi về trust, QoS hoặc cấu trúc mạng:

- **Kịch bản 1 - luồng bình thường**: `python scripts/run_scenario_s1.py`
- **Kịch bản 2 - suy giảm trust và đổi đường**: `python scripts/run_scenario_s2.py`
- **Kịch bản 3 - thay đổi telemetry/QoS**: `python scripts/run_scenario_s3.py`
- **Kịch bản 4 - vi phạm SLA độ trễ**: `python scripts/run_scenario_s4.py`
- **Kịch bản 5 - cô lập node có BN bất thường**: `python scripts/run_scenario_s5.py`

### 5. Chạy benchmark

So sánh các thuật toán đường cơ sở:

- `SP-Routing`
- `QoS-Routing`
- `Seg-Routing`
- `ZT-Routing`
- `ZT-SR-VI`

```bash
python scripts/run_baselines.py
```

Kết quả của thuật toán sẽ sinh ra biểu đồ và file dữ liệu `.csv` lưu trong thư mục `results/`.

### 6. Xuất CSV tính toán chi tiết

```bash
python scripts/export_calculation_csvs.py
```

Các CSV quan trọng nằm trong `results/calculations/`, bao gồm bảng thống kê cuối cùng `final_baseline_statistics_validation_flow.csv`.

## Tài liệu phân tích kết quả

Đọc [../docs/PHAN_TICH_KET_QUA_VA_QUY_TRINH.md](../docs/PHAN_TICH_KET_QUA_VA_QUY_TRINH.md) để xem quy trình hai tầng đồ thị, công thức QoS/trust/BN/AB, hình minh họa path `14 -> 5` và bảng so sánh cuối cùng giữa các baseline.
