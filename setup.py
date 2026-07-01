from setuptools import setup, find_packages

setup(
    name="agentic-cli",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "gradio_client",
        "rich",
    ],
    entry_points={
        "console_scripts": [
            "agentic-cli=agentic_cli.main:main",
        ],
    },
)
