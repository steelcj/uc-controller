# Contributors

## Changes

Record every change worth telling the people who use this repository under `## [Unreleased]` in `CHANGELOG.md`, as the work is done. The release scripts never write changelog entries.

## Versions

The repository's version is in `VERSION`, and follows [Semantic Versioning](https://semver.org/). It changes only when a release is cut, through `scripts/cut-release.py`, which calls `scripts/bump-version.py`.

Documents under `en/docs/` carry their own versions, independent of the repository's version. A document's version changes when the document changes, by hand, as part of that change.

## Releases

Cut and publish releases as described in [Cut and Publish a Release](en/docs/guides/releases/cut-and-publish-a-release.md). Tags and releases are never reused: a mistake is fixed in the next version.
