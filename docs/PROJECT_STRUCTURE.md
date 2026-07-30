# Cấu trúc repository

```text
.
├── emulation/
│   ├── config/
│   │   └── underlay.yaml
│   ├── images/
│   │   └── router/
│   ├── scripts/
│   ├── tests/
│   └── underlay/
├── docs/
│   ├── README.md
│   ├── PROJECT_STRUCTURE.md
│   └── phuong_phap_trien_khai_zt_sr_sdwan_containernet.md
├── .gitignore
└── README.md
```

`emulation/runtime/`, `emulation/vendor/`, `.venv/`, cache Python và packet
capture là artifact local, có thể tái tạo và không được đưa lên Git.
