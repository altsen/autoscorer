import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))
from autoscorer.cli import app

if __name__ == "__main__":
    # 支持直接在项目根目录运行 main.py
    # sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))
    app()
