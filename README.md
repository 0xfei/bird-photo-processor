# bird-photo-processor

拍鸟照片过滤器 - 重复检测、质量评估与鸟类识别工具

## 功能特点

- **重复检测**: 基于感知哈希算法 (PHash) 检测相似/重复照片
- **智能去重**: 支持删除/分组/不处理三种模式
- **质量评估**: 使用 BRISQUE 算法评估照片质量 (0-100分)
- **鸟类识别**: 本地 Birder 库 + iNaturalist API 双重支持
- **文件整理**: 按物种/日期自动分类目录
- **智能过滤**: 每种鸟类至少保留指定数量照片
- **报告导出**: 支持 JSON/CSV/HTML/Markdown 格式
- **安全操作**: 支持 dry-run 模式，所有删除进入回收站

## 快速开始

### 1. 安装依赖

```bash
# 克隆项目
git clone https://github.com/yourusername/bird-photo-processor
cd bird-photo-processor

# 运行构建脚本
bash build.sh

# 或手动安装
python3 -m venv venv
source venv/bin/activate
pip install -e ".[all]"

# 可选: 下载 Birder 模型
python -m birder.tools download-model mvit_v2_t
```

### 2. 运行演示

```bash
# 交互式演示菜单
bash run_demos.sh

# 或单独运行
bash demo_scan.sh      # 基本扫描和报告
bash demo_group.sh     # 分组重复照片
bash demo_organize.sh  # 按物种/日期整理
```

### 3. 基本命令

```bash
# 扫描目录
python -m src.cli scan /path/to/photos

# 导出报告
python -m src.cli scan /path/to/photos -e report.html

# 分组重复照片（不删除，复制到目录）
python -m src.cli group /path/to/photos -o duplicates

# 整理到分类目录
python -m src.cli organize /path/to/photos /output/dir
```

## 命令行用法

| 命令 | 说明 |
|------|------|
| `scan PATH` | 扫描目录并处理照片 |
| `group PATH` | 分组重复照片到目录 |
| `organize PATH OUT` | 整理照片到分类目录 |
| `device` | 扫描已连接的存储设备 |
| `config show` | 显示当前配置 |
| `config set KEY VALUE` | 修改配置项 |
| `status` | 显示状态信息 |

### 常用选项

| 选项 | 说明 |
|------|------|
| `--dry-run` | 模拟运行，不实际修改文件 |
| `-v, --verbose` | 显示详细日志 |
| `-e, --export FILE` | 导出报告 |
| `--skip-dedup` | 跳过重复检测 |
| `--skip-quality` | 跳过质量评估 |
| `--skip-recognize` | 跳过鸟类识别 |

## 配置说明

### 去重配置 (dedup)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `threshold` | 0.90 | 相似度阈值 (0-1) |
| `algorithm` | phash | 哈希算法: phash/dhash/ahash/whash |
| `species_aware` | true | 启用鸟种辅助判断 |
| `time_interval` | 300 | 最小时间间隔(秒) |
| `mode` | group | 模式: delete/group/none |
| `group_output_dir` | duplicates | 分组输出目录 |

### 质量配置 (quality)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `threshold` | 40.0 | BRISQUE 阈值 |
| `enabled` | true | 是否启用 |

### 识别配置 (recognizer)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `type` | birder | 类型: birder/api/both |
| `model` | mvit_v2_t | Birder 模型 |

### 整理配置 (organize)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `by_species` | true | 按物种分类 |
| `by_date` | true | 按日期分类 |
| `min_quality_for_keep` | 40.0 | 最低保留质量 |
| `min_species_images` | 1 | 每种最少保留数量 |

### 配置示例

```bash
# 查看配置
python -m src.cli config show

# 修改配置
python -m src.cli config set dedup.threshold 0.85
python -m src.cli config set dedup.mode group
python -m src.cli config set dedup.species_aware true
python -m src.cli config set quality.threshold 35
```

## 技术解释

### 1. 感知哈希 (Perceptual Hash)

感知哈希通过分析图像内容生成"指纹"，相似的图像会有相似的哈希值。

- **PHash**: 对小幅变化敏感，适合检测几乎相同的照片
- **DHash**: 速度最快，对缩放敏感
- **AHash**: 基于平均亮度，对模糊敏感
- **WHash**: 基于小波变换，对水印敏感

### 2. BRISQUE 质量评估

BRISQUE (Blind/Referenceless Image Spatial Quality Evaluator) 是一种无参考图像质量评估算法:

- **分数范围**: 0-100 分
- **分数越低**: 质量越好
- **阈值建议**: 
  - < 40: 低质量
  - 40-60: 中等质量
  - > 60: 高质量

### 3. 智能去重逻辑

```
如果启用了 species_aware:
    - 不同鸟种 → 不会被判定为重复
    - 同一鸟种 + 短时间拍摄 → 不会被删除 (连拍保护)
    - 同一鸟种 + 长时间 + 高相似度 → 判定为重复
```

### 4. 鸟类识别

- **Birder**: 本地 PyTorch 模型，完全离线
- **iNaturalist API**: 需要 API Key，可作为回退方案

## 项目结构

```
bird-photo-processor/
├── src/
│   ├── cli.py              # CLI 入口
│   ├── api/
│   │   └── inaturalist.py # iNaturalist API
│   ├── processor/
│   │   ├── dedup.py       # 去重引擎
│   │   ├── quality.py      # 质量评估
│   │   ├── recognizer.py   # 鸟类识别
│   │   ├── organizer.py    # 文件整理
│   │   └── engine.py       # 处理引擎
│   ├── scanner/
│   │   └── directory.py    # 目录扫描
│   └── utils/
│       ├── config.py       # 配置管理
│       ├── models.py       # 数据模型
│       └── report.py       # 报告生成
├── tests/                   # 测试
├── demo_*.sh               # 演示脚本
├── build.sh               # 构建脚本
├── run.sh                 # 快速运行
├── run_demos.sh           # 演示菜单
└── pyproject.toml
```

## 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_scanner.py

# 带覆盖率
pytest --cov=src --cov-report=html
```

## 常见问题

### Q: 去重灵敏度太高，摇头晃脑的照片被删了？

A: 降低相似度阈值，并启用鸟种辅助判断：
```bash
python -m src.cli config set dedup.threshold 0.7
python -m src.cli config set dedup.species_aware true
python -m src.cli config set dedup.time_interval 600  # 10分钟
```

### Q: 不想删除照片只想分组？

A: 使用 group 命令：
```bash
python -m src.cli group /path/to/photos -o duplicates
```

### Q: 如何恢复误删的照片？

A: 使用回收站模式，文件会在系统回收站中：
```bash
python -m src.cli config set file.use_trash true
```

## 许可证

MIT License
