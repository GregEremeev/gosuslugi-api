from setuptools import setup, find_packages


requirements = [
    r.strip() for r in open('requirements.txt').readlines() if '#' not in r]


setup(
    name='gosuslugi-api',
    author='Greg Eremeev',
    author_email='gregory.eremeev@gmail.com',
    version='0.7.0',
    license='BSD-3-Clause',
    url='https://github.com/GregEremeev/gosuslugi-api',
    install_requires=requirements,
    description='Toolset to work with dom.gosuslugi.ru API',
    packages=find_packages(),
    extras_require={'dev': ['ipdb==0.12.2', 'pytest==5.2.1']},
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython'
    ],
    zip_safe=False,
    include_package_data=True
)
