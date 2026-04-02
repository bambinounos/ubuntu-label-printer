from setuptools import setup, find_packages

setup(
    name="ubuntu-label-printer",
    version="0.1.0",
    description="Aplicación Ubuntu para diseñar e imprimir etiquetas",
    author="Antigravity Google",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "PyGObject>=3.42.0",
        "pycairo>=1.20.0",
    ],
    entry_points={
        "console_scripts": [
            "label-printer=src.main:main",
        ],
    },
)
