from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("karton-file-detection")

except PackageNotFoundError:
    __version__ = "unknown"

finally:
    del version, PackageNotFoundError
