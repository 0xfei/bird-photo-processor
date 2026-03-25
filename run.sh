#!/bin/bash

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Show help if no arguments
if [ $# -eq 0 ]; then
    echo "🐦 bird-photo-processor"
    echo ""
    echo "用法:"
    echo "  ./run.sh gui [path]           启动 GUI (可选指定目录)"
    echo "  ./run.sh scan <dir>           扫描并处理照片"
    echo "  ./run.sh organize <dir>       整理照片到物种/日期目录"
    echo "  ./run.sh group <dir>          分组重复照片"
    echo "  ./run.sh config show          显示当前配置"
    echo ""
    echo "示例:"
    echo "  ./run.sh gui                  启动 GUI"
    echo "  ./run.sh gui ~/Photos/Birds   启动 GUI 并打开目录"
    echo "  ./run.sh scan ~/Photos -v     扫描目录 (详细输出)"
    exit 0
fi

exec python -m src.cli "$@"
