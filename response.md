## Changelog for tqdm Repository

### Version 2.1.0 (2015-11-09)
#### New Features & API Additions
- Added `smoothing` parameter to the `tqdm` class constructor, allowing for exponential moving average smoothing for speed estimates (commit `18c0111`).
  
#### Bug Fixes & Edge Cases
- No specific bug fixes were noted in this release.

#### Architecture, Refactoring & Packaging
- No significant architectural changes were made in this release.

#### Testing, CI & Documentation
- Documentation improvements in `README.rst` to clarify the `tqdm` parameters and usage examples (commit `18c0111`).

---

### Version 2.0.0 (2015-10-30)
#### New Features & API Additions
- Introduced `dynamic_ncols` parameter to the `tqdm` class constructor, which allows the progress bar width to adjust dynamically based on the terminal size (commit `55863dc`).
- Updated the `Makefile` to include new commands for building and testing (commit `bee450d`).

#### Bug Fixes & Edge Cases
- Resolved conflicts in various files during the merge, ensuring compatibility with the latest changes (commit `9153376`).

#### Architecture, Refactoring & Packaging
- Refactored the `_tqdm.py` and `_utils.py` files to improve the handling of console width detection across different operating systems (commit `9153376`).
- Cleaned up the build process by removing unnecessary files from the build output (commit `e3ae449`).

#### Testing, CI & Documentation
- Expanded test cases in `tests/tests_tqdm.py` to cover new features and ensure stability (commit `9153376`).
- Updated the `CONTRIBUTE` and `RELEASE` files to reflect changes in the build and testing process (commit `bee450d`).

---

### Version 2.0.0-dev (2015-10-29)
#### New Features & API Additions
- Bumped version to `2.0.0-dev` in `_version.py` to indicate ongoing development (commit `55863dc`).

#### Bug Fixes & Edge Cases
- Addressed merge conflicts in `README.rst` and other files to ensure a smooth integration of features (commit `55863dc`).

#### Architecture, Refactoring & Packaging
- Updated the `Makefile` to streamline the build and testing commands (commit `bee450d`).

#### Testing, CI & Documentation
- Minor updates to documentation and examples to reflect the new features (commit `55863dc`).

---

### Additional Notes
- The repository underwent significant documentation improvements and feature additions during this period, particularly focusing on enhancing the user experience with the `tqdm` progress bar.
- The introduction of `dynamic_ncols` and `smoothing` parameters in the `tqdm` class constructor represents a notable enhancement in usability, allowing users to have a more flexible and informative progress display.