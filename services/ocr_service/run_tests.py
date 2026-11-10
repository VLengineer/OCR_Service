#!/usr/bin/env python3
"""Wrapper script to clean environment before running pytest."""
import os
import sys

# Remove problematic environment variables
for var in ["ocr_service_bind_ip", "ocr_service_port", "ocr_log_level"]:
    os.environ.pop(var, None)

# Change to ocr_service directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Run pytest
import pytest
sys.exit(pytest.main(["tests/", "-v"]))
