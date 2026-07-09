# Cấu trúc dự án

Kho mã nguồn được tổ chức để có thể đọc và kiểm chứng công khai, đồng thời loại các bản thảo riêng và thông tin bí mật khỏi hệ thống quản lý phiên bản.

## Phần lõi công khai

```text
zt_sr_sdwan/
├── src/          Module lõi của khung mô phỏng
├── scripts/      Script chạy lại benchmark, scenario và export dữ liệu
├── tests/        Bộ kiểm thử Pytest
├── config/       Policy và hyperparameter dạng YAML
├── data/         Fixture nhỏ được phép công khai
└── results/      CSV/PNG kết quả đã chọn lọc
```

## Module hỗ trợ

```text
audit_system/     Hệ thống hỗ trợ audit/refactor
docs/             Tổng quan dự án, ghi chú cấu trúc, báo cáo chi tiết và hình minh họa
docs/assets/      Sơ đồ quy trình, sơ đồ hai tầng graph và hình path theo kịch bản
```

## File/thư mục bị loại khỏi Git

Các nhóm sau được loại khỏi Git:

- `.env`, `.env.*`, token Kaggle/NVD.
- Python cache, pytest cache và build artifact.
- Dữ liệu thô hoặc dữ liệu tải về trong `zt_sr_sdwan/data/nvd`, `zt_sr_sdwan/data/traffic` và `zt_sr_sdwan/data/network_traffic_dataset.csv`.
- Bản thảo nghiên cứu riêng: `Knowledge/`, `NoiDungNghienCu_Nha/`.
- Thư mục báo cáo cũ ở local: `doc/`; bản công khai đã được copy sang `docs/reports/`.
- Prompt/fix/check local: `Fix/`, `check/`, `.agents/`.
- Artifact LaTeX/presentation build.
- Artifact model/runtime như `*.pt`, `*.pkl`, `runs/`, `wandb/`, `logs/`.

## Vì sao vẫn đưa kết quả lên

Phần lớn output sinh tự động bị ignore. Tuy nhiên các kết quả đã chọn lọc trong `zt_sr_sdwan/results/` được giữ lại để người đọc có thể kiểm chứng dự án mà không cần chạy toàn bộ pipeline:

- Bảng CSV benchmark.
- CSV minh chứng BN/AB và robustness metrics.
- Hình PNG trực quan hóa topology và attack graph.
- Hình trong `docs/assets/` để giải thích quy trình và kịch bản kiểm chứng.

Dữ liệu thô và thông tin bí mật vẫn bị loại khỏi Git.
