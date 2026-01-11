from setuptools import find_packages, setup


setup(
    name="dext",
    version="0.1.0",
    description="Exchange normalization support library (trade-side)",
    python_requires=">=3.9",
    packages=find_packages(include=["api", "api.*", "dext", "dext.*"]),
    py_modules=["config", "logger"],
    include_package_data=True,
)
