from setuptools import setup, find_packages

setup(
    name='ezocc',
    version='0.0.1',
    package_dir={'': 'src'},
    packages=find_packages(where="src/ezocc", include=['ezocc', 'ezocc.*']),
    install_requires=[
    ]
)

