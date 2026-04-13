"""
setup.py - Bắt buộc dùng để hỗ trợ `pip install -e .` (legacy editable mode).

Legacy editable mode tạo file .pth trỏ trực tiếp vào thư mục source,
thay vì hardcode đường dẫn tuyệt đối như compat editable mode mặc định
của setuptools >= 64, tránh lỗi ModuleNotFoundError khi di chuyển thư mục.
"""
from setuptools import setup

setup()
