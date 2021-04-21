import setuptools


with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()


setuptools.setup(
    name="compgrid",
    version="0.1.0",
    author="Marek Stepniowski",
    author_email="marek@ro.co",
    description="Metric Comparison Grids",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Ro-Data/compgrid/issues",
    project_urls={
        "Bug Tracker": "https://github.com/Ro-Data/compgrid/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "numpy>=1.18",
        "structlog>=21.1",
        "cryptography>=3.4.4",
        "SQLAlchemy>=1.3.13,<2",
        "snowflake-connector-python>=2.3.10",
        "snowflake-sqlalchemy>=1.2.3",
        "yagmail==0.14.245",
        "PyYAML>=5.3,<6",
        "pandas>=1.2.4,<2",
        "slack-sdk>=3.1.0,<4",
        "Jinja2>=2.11.2,<3",
        "pytest>=6.0",
        "Pillow>=8.1.0",
    ],
)
