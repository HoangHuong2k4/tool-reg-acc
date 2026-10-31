#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os

# Thêm thư mục gốc vào PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.bots.x_grok_hunter import main

if __name__ == "__main__":
    main()

