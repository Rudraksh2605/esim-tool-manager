"""
eSim Tool Manager — Package Setup.

Provides `pip install -e .` support and the `esim-tool-manager` console script.
"""

from setuptools import setup, find_packages
from pathlib import Path

long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="esim-tool-manager",
    version="1.0.0",
    description="Automated CLI tool manager for the eSim EDA ecosystem",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="eSim Team",
    python_requires=">=3.10",
    packages=find_packages(),
    include_package_data=True,
    package_data={"tool_manager": ["config/*.json"]},
    install_requires=[
        "click>=8.1",
        "rich>=13.0",
        "packaging>=23.0",
        "customtkinter>=5.2",
        "Pillow>=10.0",
        "py7zr>=0.22",
    ],
    entry_points={
        "console_scripts": [
            "esim-tool-manager=tool_manager.main:main",
        ],
        "gui_scripts": [
            "esim-tool-manager-gui=tool_manager.gui.app:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Build Tools",
    ],
)
