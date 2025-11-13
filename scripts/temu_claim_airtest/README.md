# Temu 认领 Airtest 组件

该组件使用 [Airtest](https://airtest.netease.com/) 对妙手 ERP 页面执行“认领到 → Temu 全托管 → 确定”的交互。它可以作为 Playwright 流程的子步骤，在定位器不稳定的场景下提供更可靠的视觉识别能力。

## 目录结构

```
scripts/temu_claim_airtest/
├── README.md
├── .ai.json
├── launcher.py               # Python 调用入口 (run_airtest_claim)
├── examples/
│   └── run_via_python.py     # 调用示例
└── temu_claim.air/
    ├── __init__.py
    ├── script.py             # Airtest 主脚本
    └── templates/            # 模板图片目录
        ├── README.md         # 模板采集说明
        ├── toolbar_claim_button.png
        ├── temu_checkbox.png
        ├── confirm_button.png
        └── dialog_close.png (可选)
```

## 截图模板

Airtest 通过模板匹配识别控件，请按照 `templates/README.md` 的说明，使用 AirtestIDE 或系统截图工具截取以下控件的 PNG 图片：

- 顶部工具栏“认领到”按钮
- 认领弹窗中的“Temu全托管”勾选项
- 认领弹窗底部的“确定”按钮
- （可选）弹窗右上角的“关闭”图标

模板文件应存放在 `templates/` 目录下。

## 运行方式

### 1. 直接调用脚本

```bash
pip install airtest pocoui
python scripts/temu_claim_airtest/temu_claim.air/script.py \
    --device OSX:/// \
    --args "product_count=5 iterations=4 template_dir=scripts/temu_claim_airtest/temu_claim.air/templates"
```

### 2. 在 Python 代码中调用

```python
from scripts.temu_claim_airtest.launcher import run_airtest_claim

run_airtest_claim(product_count=5, iterations=4)
```

默认情况下会连接到当前 macOS 桌面 (`OSX:///`)。如果需要控制其它显示环境，可以通过 `device_uri` 参数传入 Airtest 支持的 URI。

## 注意事项

- 运行脚本前请确认浏览器已经打开并显示在前台，分辨率与缩放比例与截取模板时保持一致。
- 模板匹配对主题/暗色模式敏感，如界面变化，请重新截取对应 PNG。
- 如需调整识别阈值或等待时间，可在 `script.py` 中的 `DEFAULT_THRESHOLDS`、`wait_and_touch` 函数或运行参数中进行设置。
