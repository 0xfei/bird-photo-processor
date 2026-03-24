#!/bin/bash
# Demo script: Basic scan and report

set -e

# Activate venv if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "======================================"
echo "🐦 Demo 1: 基本扫描和报告"
echo "======================================"

# Create test images
mkdir -p demo_photos
for i in $(seq 1 5); do
    python3 -c "
from PIL import Image
import random
img = Image.new('RGB', (200, 200), color=($((random.randint(50, 200))), $((random.randint(50, 200))), $((random.randint(50, 200)))))
img.save('demo_photos/photo_$i.jpg')
"
done

echo "创建了 5 张测试图片"

# Run scan
echo ""
echo "运行扫描..."
python -m src.cli scan demo_photos -v

# Export report
echo ""
echo "导出报告..."
python -m src.cli scan demo_photos -e demo_report.html

echo ""
echo "✅ Demo 1 完成!"
echo "   报告文件: demo_report.html"
