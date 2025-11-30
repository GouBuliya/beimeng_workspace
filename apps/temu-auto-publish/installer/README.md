# 安装包构建指南

本目录包含构建**单个 exe 安装程序**的所有工具，让用户无需安装任何依赖即可使用。

## 📦 输出产物

| 文件 | 大小 | 说明 |
|------|------|------|
| `TemuWebPanel_Setup_x.x.x.exe` | ~300MB | 安装程序（推荐） |
| `TemuWebPanel_Portable.7z` | ~250MB | 便携版压缩包 |

## 🚀 一键打包

### 方式一：一键脚本（推荐）

```batch
cd apps\temu-auto-publish
installer\build_all.bat
```

脚本会自动：
1. 构建便携版（含 Python + 依赖 + 浏览器）
2. 创建 Inno Setup 安装程序（如果已安装）
3. 创建 7z 压缩包（如果已安装 7-Zip）

### 方式二：手动步骤

```batch
# 1. 构建便携版
python installer\build_portable.py

# 2. 创建安装程序（需要 Inno Setup）
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\installer.iss

# 3. 或创建压缩包（需要 7-Zip）
cd build\portable
"C:\Program Files\7-Zip\7z.exe" a -t7z -mx=9 ..\..\dist\TemuWebPanel_Portable.7z TemuWebPanel
```

## 📋 构建要求

### 必需

- Windows 10/11 x64
- Python 3.12+
- 网络连接（下载依赖）

### 可选（用于创建安装程序）

- [Inno Setup 6](https://jrsoftware.org/isdl.php) - 创建 exe 安装程序
- [7-Zip](https://www.7-zip.org/) - 创建压缩包

## 📁 便携版目录结构

```
TemuWebPanel/
├── python/                 # 嵌入式 Python 3.12
├── Lib/site-packages/      # Python 依赖包
├── browsers/               # Playwright Chromium 浏览器
├── app/                    # 应用代码
│   ├── src/
│   ├── web_panel/
│   └── config/
├── data/                   # 数据目录
│   ├── input/              # 输入文件
│   ├── output/             # 输出结果
│   └── logs/               # 日志
├── TemuWebPanel.bat        # 启动脚本（自动打开浏览器）
├── 启动_TemuWebPanel.bat   # 启动脚本（仅控制台）
└── .env.example            # 配置模板
```

## 🔧 自定义配置

### 修改版本号

编辑 `installer.iss`：

```ini
#define AppVersion "1.0.0"
```

### 修改应用名称

编辑 `build_portable.py` 和 `installer.iss`：

```python
APP_NAME = "TemuWebPanel"
```

### 添加图标

1. 准备 `.ico` 图标文件
2. 放到 `data/image/icon.ico`
3. 重新构建

## ❓ 常见问题

### Q: 打包后 exe 很大（300MB+）？

A: 正常，因为包含了：
- Python 运行时 (~30MB)
- Python 依赖包 (~100MB)
- Chromium 浏览器 (~150MB+)

### Q: 如何减小体积？

1. 使用 UPX 压缩：
```batch
upx --best build\portable\TemuWebPanel\python\*.dll
```

2. 删除不需要的浏览器（只保留 Chromium）

### Q: 安装程序被杀毒软件误报？

A: 这是常见的误报，因为 PyInstaller 打包的程序经常被误报。解决方案：
1. 对 exe 进行代码签名
2. 提交到杀毒软件厂商白名单
3. 告知用户添加例外

### Q: 用户运行报错缺少 DLL？

A: 确保用户系统安装了 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

## 📝 发布清单

发布前检查：

- [ ] 更新版本号
- [ ] 测试便携版能正常运行
- [ ] 测试安装程序安装/卸载
- [ ] 在干净的 Windows 系统测试
- [ ] 准备更新日志


