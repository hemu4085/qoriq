from pathlib import Path
from setuptools import setup, find_packages

HERE = Path(__file__).parent
VERSION_FILE = HERE / "VERSION"
version = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "1.2.0"

setup(
    name="qoriq",
    version=version,
    description="Data quality scoring and fixer tools",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
)