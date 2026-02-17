from setuptools import setup, find_packages

setup(
    name="subtitles",
    version="1.0.0",
    description="Subtitle extraction, translation, and synchronization toolkit",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "ffmpeg-python>=0.2.0",
        "srt>=3.5.0",
        "deep-translator>=1.11.0",
        "pyyaml>=6.0",
        "customtkinter>=5.2.0",
    ],
    python_requires=">=3.12",
    entry_points={
        "console_scripts": [
            "subtitles=subtitles.__main__:main",
            "subtitles-gui=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Video",
        "Topic :: Text Processing :: Linguistic",
    ],
    keywords="subtitles translation ffmpeg srt video",
    py_modules=["main"],
)
