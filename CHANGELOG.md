# Changelog

## [1.0.1] - 2026-01-17

### Fixed
- Fixed missing `logger` definition in `filterupdate_lite.py` that caused NameError on execution.
- Fixed file handle bug in `get_config_with_bgpq4()` in lite version where subprocess wrote to a closed file handle.
- Fixed missing imports in `setup.py` (`subprocess`, `platform`, `argparse`).
- Fixed incorrect `Path.write()` call in `filterupdate.py` - changed to `Path.write_text()`.
- Removed erroneous `sys.exit(2)` at end of `main()` in `filterupdate.py` that incorrectly signaled failure.

## [1.0.0] - 2026-01-17

### Added
- Modernized `filterupdate.py` with `pathlib`, type hints, logging, and `subprocess.run`.
- Modernized `filterupdate_lite.py` with `pathlib`, type hints, logging, and `subprocess.run`.
- Updated `requirements.txt` with latest package versions.
- Updated `setup.py` to use `setuptools` and modern packaging practices.
- Added comprehensive docstrings throughout the codebase.
- Enhanced `README.md` with recent usage examples and improved formatting.

### Changed
- Replaced all `print` statements with `logging` module usage.
- Updated code to Python 3.8+ standards and best practices.
- Improved error handling and edge case coverage.

### Fixed
- Fixed potential resource leaks in subprocess calls.
- Ensured consistent logging configuration across modules.
