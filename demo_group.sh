#!/bin/bash
# Demo script: Group duplicates into directories

set -e

# Activate venv if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "======================================"
echo "🐦 Demo 2: 分组重复照片到目录"
echo "======================================"

# Create test images (some similar)
mkdir -p demo_group
python3 -c "
from PIL import Image
# Create similar images
for i in $(seq 1 3); do
    img = Image.new('RGB', (200, 200), color=(100, 100, 100))
    img.save('demo_group/similar_$i.jpg')
done
# Create different images
for i in $(seq 1 2); do
    img = Image.new('RGB', (200, 200), color=(200, 100, 100))
    img.save('demo_group/different_$i.jpg')
done
"

echo "创建了 5 张测试图片 (3张相似, 2张不同)"

# Run group command in dry-run mode
echo ""
echo "运行分组 (dry-run)..."
python -m src.cli group demo_group --dry-run -o duplicates

echo ""
echo "✅ Demo 2 完成!"
echo "   运行时不加 --dry-run 才会真正复制文件"
