#!/bin/bash
# Demo script: Organize photos by species and date

set -e

# Activate venv if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "======================================"
echo "🐦 Demo 3: 按物种/日期整理照片"
echo "======================================"

# Create test images
mkdir -p demo_organize
python3 -c "
from PIL import Image
from datetime import datetime, timedelta
import os
import time

base_time = time.time()

# Create images with different "dates"
for i in $(seq 1 3); do
    img = Image.new('RGB', (200, 200), color=(100, 100 + i*30, 100))
    img.save('demo_organize/bird_$i.jpg')
    # Set file time
    os.utime('demo_organize/bird_$i.jpg', (base_time - i*86400, base_time - i*86400))
done

# Create landscape
img = Image.new('RGB', (200, 200), color=(100, 200, 100))
img.save('demo_organize/landscape.jpg')
os.utime('demo_organize/landscape.jpg', (base_time, base_time))
"

echo "创建了 4 张测试图片"

# Run organize in dry-run mode
echo ""
echo "运行整理 (dry-run)..."
python -m src.cli organize demo_organize organized_photos --dry-run

echo ""
echo "✅ Demo 3 完成!"
echo "   运行时不加 --dry-run 才会真正移动文件"
