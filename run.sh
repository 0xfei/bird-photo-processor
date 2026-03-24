#!/bin/bash

# Quick run script for bird-photo-processor

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run CLI
exec python -m src.cli "$@"
