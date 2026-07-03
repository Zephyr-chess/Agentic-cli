from setuptools import setup, find_packages

setup(
    name="agentic-cli",
    version="1.5.0",
    packages=find_packages(),
    install_requires=[
        "rich",
        "requests",
        "prompt-toolkit",
        "questionary",
    ],
    entry_points={
        "console_scripts": [
            "agentic-cli=agentic_cli.main:main",
        ],
    },
)
