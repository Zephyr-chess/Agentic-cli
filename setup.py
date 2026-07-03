from setuptools import setup, find_packages

setup(
    name="agentic-cli",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "rich",
        "requests",
        "textual",
        "questionary",
    ],
    entry_points={
        "console_scripts": [
            "agentic-cli=agentic_cli.main:main",
        ],
    },
)
