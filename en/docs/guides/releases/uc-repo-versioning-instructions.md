# uc-repo versioning instructions

**If you are not working in uc-repo** specifically you can **ignore** or, better yet **delete this file**

## Description

uc-repo keeps its own version and changelog in `.uc-repo/`, apart from the root `VERSION` and `CHANGELOG.md`. The root files always stay in their fresh-start state, `0.0.0` and an empty Unreleased section, because every repository created from the template starts with a copy of them. The release scripts only read the root files, so they never change `.uc-repo/`.

A new version of uc-repo is made by hand: raise `.uc-repo/VERSION`, add a dated section to `.uc-repo/CHANGELOG.md`, then commit, tag `v<version>`, and push the commit and the tag. Tags are not copied into new repositories.

Every repository created from the template receives a copy of `.uc-repo/`, which records the template version it started from. Leave it unchanged there: it shows which later template changes the repository does not have.

In `uc-repo`:

```sh
mkdir .uc-repo
echo 0.1.0 > .uc-repo/VERSION
cat > .uc-repo/CHANGELOG.md <<'EOF'
# uc-repo Changelog

## [0.1.0] - 2026-11-23

### First version

Release scripts, the Cut and Publish a Release guide, CONTRIBUTORS.md, and fresh-start VERSION and CHANGELOG.md.
EOF
git add .uc-repo
git commit -m "Record uc-repo's own version"
git tag -a v0.1.0 -m "uc-repo 0.1.0"
git push && git push origin v0.1.0
```

Each time you change the template:

1. Make the change. Never edit the root `VERSION` or `CHANGELOG.md`.
2. Raise `.uc-repo/VERSION`.
3. Add a dated section for that version to `.uc-repo/CHANGELOG.md`.
4. Commit, tag `v<version>`, and push the commit and the tag.

In a new repository, don't edit `.uc-repo/`. It records the template version the repository came from.
