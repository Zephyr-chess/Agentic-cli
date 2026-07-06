from setuptools import setup, find_packages

setup(
    name="agentic-cli",
    version="3.0.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "agentic_cli": ["web/templates/*.html", "web/static/*", "web/*.py"],
    },
    install_requires=[
        "rich",
        "requests",
        "flask",
        "flask-cors",
        "questionary",
        "prompt-toolkit",
    ],
    entry_points={
        "console_scripts": [
            "agentic-cli=agentic_cli.main:main",
        ],
    },
)
