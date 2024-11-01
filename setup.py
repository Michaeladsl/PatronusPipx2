from setuptools import setup, find_packages
import os

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
    include_package_data=True, 
    entry_points={
        'console_scripts': [
            'patronus=patronus:main',         
            'patronus-edit=edit:main',         
            'patronus-redact=redact:main',
            'patronus-split=split:main',
            'patronus-server=server:main',
        ],
    },
    package_data={
        '': ['configure.sh'],
    },
    data_files=[
        ('', ['configure.sh']),  
        ('static', gather_static_files()),  
    ],
)