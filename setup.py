"""Setup script for truex_sharing SDK package."""

from setuptools import setup, find_packages

setup(
    name="truex-sharing-sdk",
    version="0.1.0",
    description="TrueX OPENAPI CUBE SDK for Tuya grant_type=1",
    packages=find_packages(include=["truex_sharing", "truex_sharing.*"]),
    python_requires=">=3.11",
    install_requires=[
        "aiohttp",
    ],
)
