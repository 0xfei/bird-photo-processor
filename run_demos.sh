#!/bin/bash
# Main demo runner - runs all demos

set -e

echo "======================================"
echo "🐦 bird-photo-processor 演示脚本"
echo "======================================"
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "错误: 请先运行 build.sh 创建虚拟环境"
    exit 1
fi

source venv/bin/activate

# Show menu
echo "请选择演示:"
echo "  1) 基本扫描和报告 (scan + export)"
echo "  2) 分组重复照片 (group duplicates)"
echo "  3) 按物种/日期整理 (organize)"
echo "  4) 运行所有演示"
echo "  0) 退出"
echo ""

read -p "请输入选项 [1-4]: " choice

case $choice in
    1)
        echo "运行演示 1..."
        bash demo_scan.sh
        ;;
    2)
        echo "运行演示 2..."
        bash demo_group.sh
        ;;
    3)
        echo "运行演示 3..."
        bash demo_organize.sh
        ;;
    4)
        echo "运行所有演示..."
        bash demo_scan.sh
        echo ""
        bash demo_group.sh
        echo ""
        bash demo_organize.sh
        ;;
    0)
        echo "退出"
        exit 0
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac

echo ""
echo "======================================"
echo "✅ 所有演示完成!"
echo "======================================"
