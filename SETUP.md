# OmniPublish V2.0 — 环境配置指南（给 Claude 读的）

本文件供 Claude Code 或 Claude AI 读取，自动帮用户完成环境配置。

## 目标

让用户在本机运行 OmniPublish，浏览器访问 http://localhost:9527 即可使用。

## 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 运行后端 |
| FFmpeg | 5.0+ | 视频水印处理（可选，不装也能用图片功能） |
| pip | 最新 | 安装 Python 包 |

**不需要**：Node.js、Docker、数据库（前端已预编译，数据库用 SQLite 内置）

## 配置步骤

### 1. 安装 Python

**Mac:**
```bash
# 方式一：Homebrew（推荐）
brew install python3

# 方式二：从官网下载
# https://www.python.org/downloads/
```

**Windows:**
```powershell
# 方式一：winget（Windows 10+ 自带）
winget install Python.Python.3.12

# 方式二：从官网下载安装
# https://www.python.org/downloads/
# ⚠️ 安装时必须勾选 "Add Python to PATH"
```

**Linux:**
```bash
sudo apt update && sudo apt install python3 python3-venv python3-pip
```

### 2. 安装 FFmpeg（可选）

**Mac:** `brew install ffmpeg`
**Windows:** `winget install Gyan.FFmpeg`
**Linux:** `sudo apt install ffmpeg`

### 3. 配置

```bash
cd OmniPublish
cp config.json.example config.json
```

config.json 中唯一需要修改的是 `api_key` 字段（AI 文案生成的 API 密钥）。
其他配置（CMS、加密、模型等）已预填，无需修改。

如果压缩包里已包含 config.json（团队内部版），则跳过此步。

### 4. 启动

**Mac/Linux:**
```bash
chmod +x start.sh
./start.sh
```

**Windows:**
```
双击 start.bat
```

start.sh/start.bat 会自动：
- 创建 Python 虚拟环境
- 安装所有 pip 依赖（包括 OpenCV、YOLOv8、FastAPI 等）
- 启动服务

### 5. 访问

浏览器打开 http://localhost:9527
默认账号：admin / admin123

## 常见问题

### pip install 报错 "Microsoft Visual C++ 14.0 is required"（Windows）
需安装 Visual Studio Build Tools：
```
winget install Microsoft.VisualStudio.2022.BuildTools
```
安装时勾选 "C++ build tools"

### "command not found: python3"（Mac）
检查 Homebrew 是否安装：
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python3
```

### 端口 9527 被占用
编辑 config.json，修改 `server.port` 为其他端口（如 8080）

### YOLOv8 模型下载慢
首次运行封面/水印功能时会自动下载 yolov8n.pt（约 6MB）。
如果下载慢，可手动下载放到项目根目录：
https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt

## 项目结构（供参考）

```
OmniPublish/
├── config.json          ← 运行时配置（api_key 在这里改）
├── config.json.example  ← 配置模板
├── start.sh             ← Mac/Linux 启动脚本
├── start.bat            ← Windows 启动脚本
├── backend/             ← FastAPI 后端（Python）
├── frontend/dist/       ← 预编译的前端（无需 Node.js）
└── docs/                ← 文档
```
