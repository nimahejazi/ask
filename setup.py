from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="nh-ask-cli",
    version="0.2.1",
    author="Nima",
    description="AI CLI tool for natural language interaction with LLMs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/anomalyco/ask",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "tomli>=2.0.0; python_version < '3.11'",
        "tomli_w>=1.0.0",
        "requests>=2.31.0",
        "questionary>=2.0.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "ask=ask.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
