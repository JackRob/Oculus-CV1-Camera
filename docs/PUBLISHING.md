# Preparing a public release

The source package is ready for review; preparing it does not publish the repository or a release.

1. Inspect the source and every archive entry. Run `python -m unittest discover -s tests -v`, repeat with `python -O`, and run `python tools/build_release.py`. Inspect `dist/SHA256SUMS.txt` and the ZIP contents.
2. Confirm the release contains no firmware images, backups, manifests, calibration, captures, local paths, private logs, credentials or serial numbers. The ZIP uses an explicit allowlist and excludes Git history. Review the synthetic tests and profile differences as source.
3. **Inspect all Git history before changing repository visibility.** Author/committer names and emails, older file versions, branches, tags, issues, Actions logs, artifacts, and prior releases can expose information absent from the current tree. A source-file scan cannot sanitize that history. If history requires replacing, preserve a private backup and obtain the repository owner's authorization first.
4. Keep the prominent **“This can and will brick your Sensor”** disclaimer, one-unit compatibility limit, and recovery limitations in the README, installer and release notes. Describe the package as experimental; do not promise universal or safe installation.
5. After explicit authorization to publish, commit the reviewed source with privacy-preserving author metadata, push it, and choose the repository's intended visibility. Do not include private workspace files. Run CI before releasing.
6. The prepared **Build draft release** workflow is manually triggered. It tests the source, creates the allowlisted ZIP and checksum, and creates a **draft** GitHub release for `v0.1.0`. A maintainer must review and publish that draft. It is not triggered by normal pushes or pull requests.

The archive contains readable source, not an opaque executable, bundled Python runtime, USB driver, or complete firmware image. It needs Python 3.11–3.13 x64 and first-run setup downloads. An unsigned source installer can still trigger Windows security prompts; do not claim code signing or disable security features to work around them.

If a future revision gains broader physical validation, record the actual devices/revisions and capture tests without publishing sensor identifiers or private imagery. Avoid importing raw development logs as evidence.
