from setuptools import setup, find_packages

setup(
    name="agentic-cli",
    version="2.2.0",
    packages=find_packages(),
    install_requires=[
        "rich",
        "requests",
        "flask",
        "flask-cors",
    ],
    entry_points={
        "console_scripts": [
            "agentic-cli=agentic_cli.main:main",
        ],
    },
)
