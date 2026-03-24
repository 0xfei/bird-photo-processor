#!/bin/bash

# bird-photo-processor build and run script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🐦 bird-photo-processor 构建脚本${NC}"
echo ""

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}错误: 需要 Python $required_version+, 当前版本: $python_version${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python 版本: $python_version"

# Check if running in project directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}错误: 请在项目根目录运行此脚本${NC}"
    exit 1
fi

# Create virtual environment if needed
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}升级 pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "${YELLOW}安装依赖...${NC}"
pip install -e ".[all]"

# Download Birder model (optional)
if click --help >/dev/null 2>&1; then
    echo -e "${YELLOW}下载 Birder 模型...${NC}"
    python -m birder.tools download-model mvit_v2_t || echo -e "${YELLOW}模型下载失败，将使用备用方案${NC}"
fi

echo ""
echo -e "${GREEN}✓ 安装完成!${NC}"
echo ""
echo "使用方法:"
echo "  source venv/bin/activate  # 激活虚拟环境"
echo "  bird-photo-processor --help"
echo ""
echo "常用命令:"
echo "  bird-photo-processor scan /path/to/photos"
echo "  bird-photo-processor config show"
echo "  bird-photo-processor organize /path/to/photos /output/dir"
