from setuptools import setup, find_packages
import os

# Helper function to gather all files within the static directory and subdirectories
def gather_static_files():
    static_files = []
    for dirpath, _, filenames in os.walk('static'):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            static_files.append(file_path)
    return static_files

setup(
    name='patronus',
    version='0.1.0',
    py_modules=['patronus', 'edit', 'split', 'redact', 'server'],
    install_requires=[
        'Flask',
        'pyte',
        'tqdm',
        'asciinema',
    ],
    include_package_data=True,  # Uses MANIFEST.in to include data files
    entry_points={
        'console_scripts': [
            'edit=edit:main',
            'patronus=patronus:main',
            'redact=redact:main',
            'server=server:main',
            'split=split:main',
        ],
    },
    package_data={
        '': ['configure.sh'],
    },
    data_files=[
        ('', ['configure.sh']),  # Ensures configure.sh is at the root
        ('static', gather_static_files()),  # Includes all files in the static directory and subdirectories
    ],
)