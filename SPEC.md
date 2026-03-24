# bird-photo-processor 规格文档

## 1. 项目概述

**项目名称**: bird-photo-processor  
**项目类型**: 命令行工具 (CLI)  
**核心功能**: 拍鸟照片的重复检测、质量评估、鸟类识别与自动整理  
**目标用户**: 观鸟爱好者、野生动物摄影师

---

## 2. 功能需求

### 2.1 图片扫描

- **目录扫描**: 递归扫描指定目录中的图片文件
- **格式支持**: JPEG, PNG, HEIC, HEIF, RAW (CR2, NEF, ARW)
- **设备监控**: 监听新插入的存储设备（读卡器/U盘），自动触发扫描

### 2.2 重复检测

- **算法**: 感知哈希 (PHash/DHash/AHash/WHash)
- **相似度阈值**: 可配置 (默认 90%)
- **处理模式**:
  - `delete`: 删除重复照片
  - `group`: 分组到目录（不删除）
  - `none`: 不处理
- **智能判断**:
  - 鸟种辅助判断：不同鸟种不算重复
  - 时间间隔保护：短时间连拍不算重复
- **保留策略**: 
  - 保留 1 张质量最高的
  - 可选保留 1 张备份（次高质量）
- **输出**: 生成重复组，供用户确认

### 2.3 质量评估

- **算法**: BRISQUE (Blind/Referenceless Image Spatial Quality Evaluator)
- **评分范围**: 0-100 分（分数越低质量越好）
- **阈值配置**: BRISQUE < 40 视为低质量
- **输出**: 为每张图片生成质量分数

### 2.4 鸟类识别

- **本地识别**: 使用 Birder 库 (PyTorch)
  - 模型: mvit_v2_t (轻量) 或更大模型
  - 无需网络，完全离线
- **远程 API**: iNaturalist API (回退方案)
  - 免费，需要 API token
  - 网络不稳定时自动切换
- **输出**: 鸟类物种名称、置信度

### 2.5 文件操作

- **删除**: 安全删除到系统回收站
- **移动**: 移动到指定目录
- **重命名**: 按物种/质量/日期重命名
- **日志**: 记录所有操作，支持撤销

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI 入口                               │
│                     (click/typer)                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  目录扫描    │ │  设备监控    │ │  配置管理    │
│  scanner/   │ │  scanner/   │ │  config.py  │
└──────┬──────┘ └─────────────┘ └─────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                      处理引擎 (processor/)                    │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│   去重      │   质量评估   │   鸟类识别   │   文件操作        │
│  dedup.py  │  quality.py │ recognizer.py│  file_ops.py     │
└──────┬──────┴──────┬──────┴──────┬──────┴───────────┬───────┘
       │             │             │                  │
       ▼             ▼             ▼                  ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  imagededup │ │   brisque   │ │   Birder    │ │    shutil   │
│             │ │             │ │ iNaturalist │ │  send2trash │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

---

## 4. 模块设计

### 4.1 CLI 模块 (cli/)

| 函数 | 功能 |
|------|------|
| `cli()` | 主命令行入口 |
| `scan_directory()` | 扫描目录命令 |
| `scan_device()` | 扫描设备命令 |
| `watch_device()` | 监听设备插入 |
| `show_results()` | 显示处理结果 |

### 4.2 扫描器模块 (scanner/)

| 函数/类 | 功能 |
|---------|------|
| `ImageScanner` | 图片扫描器类 |
| `scan_directory(path)` | 递归扫描目录 |
| `get_image_files(path)` | 获取图片文件列表 |
| `DeviceWatcher` | 设备监听器类 |
| `watch_for_devices()` | 监听新设备 |

### 4.3 处理器模块 (processor/)

| 函数/类 | 功能 |
|---------|------|
| `Deduplicator` | 去重引擎类 |
| `find_duplicates(images)` | 查找重复图片 |
| `QualityAssessor` | 质量评估器类 |
| `assess_quality(image)` | 评估单张图片质量 |
| `BirdRecognizer` | 鸟类识别器类 |
| `recognize(image)` | 识别鸟类物种 |

### 4.4 API 模块 (api/)

| 函数 | 功能 |
|------|------|
| `iNaturalistClient` | iNaturalist API 客户端 |
| `identify_species(image)` | 调用 API 识别物种 |

### 4.5 工具模块 (utils/)

| 函数/类 | 功能 |
|---------|------|
| `Config` | 配置管理类 |
| `load_config()` | 加载配置 |
| `save_config()` | 保存配置 |
| `ImageInfo` | 图片信息数据类 |
| `format_size()` | 格式化文件大小 |
| `ensure_dir()` | 确保目录存在 |

---

## 5. 数据结构

### 5.1 ImageInfo

```python
@dataclass
class ImageInfo:
    path: str                      # 文件路径
    filename: str                  # 文件名
    size: int                      # 文件大小 (bytes)
    created_time: float            # 创建时间 (timestamp)
    modified_time: float          # 修改时间 (timestamp)
    width: int                     # 图像宽度
    height: int                    # 图像高度
    format: str                    # 图像格式
    
    # 处理结果
    hash: str = None               # 感知哈希
    quality_score: float = None    # BRISQUE 质量分数
    bird_species: str = None       # 识别物种
    bird_confidence: float = None  # 置信度
    
    # 元数据
    is_duplicate: bool = False     # 是否重复
    duplicate_group: str = None    # 重复组 ID
    quality_level: str = None      # 质量等级 (high/medium/low)
```

### 5.2 ProcessingResult

```python
@dataclass
class ProcessingResult:
    total_images: int             # 总图片数
    duplicate_groups: List[List[ImageInfo]]  # 重复组
    low_quality_images: List[ImageInfo]      # 低质量图片
    recognized_images: List[ImageInfo]       # 已识别图片
    deleted_images: List[str]    # 已删除图片
    moved_images: List[str]      # 已移动图片
    duration: float              # 处理耗时 (秒)
```

### 5.3 Config

```python
@dataclass
class Config:
    # 去重配置
    similarity_threshold: float = 0.90    # 相似度阈值
    keep_best_count: int = 1             # 保留最好质量数量
    keep_backup: bool = True             # 是否保留备份
    
    # 质量配置
    quality_threshold: float = 40.0       # BRISQUE 阈值
    quality_check_enabled: bool = True   # 是否启用质量检查
    
    # 识别配置
    recognizer: str = "birder"            # 识别器 (birder/api/both)
    birder_model: str = "mvit_v2_t"      # Birder 模型
    inat_api_key: str = None             # iNaturalist API Key
    recognizer_enabled: bool = True      # 是否启用识别
    
    # 文件操作配置
    auto_delete: bool = False            # 自动删除低质量
    auto_move: bool = False              # 自动移动
    output_dir: str = None               # 输出目录
    use_trash: bool = True               # 使用回收站
    
    # 设备监控
    watch_devices: bool = False          # 监听设备
    auto_scan_on_device: bool = True    # 设备插入自动扫描
    
    # 缓存
    cache_dir: str = ".bird-processor-cache"  # 缓存目录
    use_cache: bool = True               # 是否使用缓存
```

---

## 6. 命令行接口

### 6.1 主命令

```bash
bird-photo-processor [OPTIONS] COMMAND [ARGS]...
```

### 6.2 子命令

| 命令 | 功能 |
|------|------|
| `scan PATH` | 扫描指定目录 |
| `scan --device` | 扫描已连接的存储设备 |
| `watch` | 监听设备插入并自动扫描 |
| `config` | 查看/修改配置 |
| `status` | 显示处理状态和缓存信息 |

### 6.3 选项

| 选项 | 说明 |
|------|------|
| `--dry-run` | 模拟运行，不实际修改文件 |
| `--verbose` | 显示详细日志 |
| `--parallel N` | 并行处理线程数 |
| `--format FORMAT` | 输出格式 (table/json) |

### 6.4 使用示例

```bash
# 扫描目录
bird-photo-processor scan /path/to/photos

# 扫描并自动删除低质量图片
bird-photo-processor scan /path/to/photos --auto-delete

# 监听设备
bird-photo-processor watch

# 查看配置
bird-photo-processor config show

# 修改配置
bird-photo-processor config set quality_threshold 35
bird-photo-processor config set similarity_threshold 0.85
```

---

## 7. 配置说明

### 7.1 配置文件位置

- macOS: `~/.config/bird-photo-processor/config.toml`
- Linux: `~/.config/bird-photo-processor/config.toml`
- Windows: `%APPDATA%\bird-photo-processor\config.toml`

### 7.2 默认配置

```toml
[dedup]
similarity_threshold = 0.90
keep_best_count = 1
keep_backup = true

[quality]
threshold = 40.0
enabled = true

[recognizer]
type = "birder"
model = "mvit_v2_t"
inat_api_key = ""
enabled = true

[file]
auto_delete = false
auto_move = false
output_dir = ""
use_trash = true

[device]
watch = false
auto_scan = true

[cache]
dir = ".bird-processor-cache"
enabled = true
```

---

## 8. 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| 文件不存在 | 跳过，记录警告 |
| 权限不足 | 跳过，记录错误 |
| 图片损坏 | 跳过，记录错误 |
| 识别失败 | 记录，继续处理 |
| API 超时 | 自动重试 3 次，回退到本地 |
| 磁盘空间不足 | 停止操作，提示用户 |

---

## 9. 性能优化

- **并行处理**: 使用 `concurrent.futures` 多线程处理
- **缓存机制**: 缓存图片哈希和质量分数，避免重复计算
- **增量扫描**: 只处理新增或修改的图片
- **模型优化**: 使用轻量级模型 (mvit_v2_t) 减少推理时间

---

## 10. 验收标准

### 10.1 功能验收

- [ ] 能正确扫描目录中的所有图片
- [ ] 能检测出相似度 ≥90% 的重复图片
- [ ] 能为每张图片生成 BRISQUE 质量分数
- [ ] 能使用 Birder 识别鸟类物种
- [ ] 能使用 iNaturalist API 作为回退
- [ ] 能按配置自动删除/移动文件
- [ ] 能监听设备插入并自动扫描

### 10.2 性能验收

- [ ] 1000 张图片去重在 2 分钟内完成
- [ ] 1000 张图片质量评估在 5 分钟内完成
- [ ] CLI 响应时间 < 1 秒

### 10.3 稳定性验收

- [ ] 不会因单张损坏图片导致整个任务失败
- [ ] 支持 Ctrl+C 安全中断
- [ ] 所有操作记录日志，支持撤销
