from setuptools import setup, find_packages

setup(
    name='aml_system',
    version='1.0.0',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'Flask',
        'pandas',
        'scikit-learn',
        'gunicorn',
        'waitress',
    ],
)
