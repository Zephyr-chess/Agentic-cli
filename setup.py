from setuptools import setup, find_packages

setup(
    name="agentic-cli",
    version="1.2.0",
    packages=find_packages(),
    install_requires=[
        "rich",
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "agentic-cli=agentic_cli.main:main",
        ],
    },
)
