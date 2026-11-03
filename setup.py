"""Packages `accelerator` so Dataflow workers / Composer can import it (--setup_file)."""
import setuptools

setuptools.setup(
    name="accelerator",
    version="0.1.0",
    packages=setuptools.find_packages(include=["accelerator*"]),
    install_requires=[],  # heavy deps are pre-installed on workers or lazily imported
)
