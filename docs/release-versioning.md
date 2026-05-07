# Release Versioning

Dictate uses calendar versioning for public releases:

```text
YYYY.M.D-N
```

`N` is the release sequence for that date. The first release on May 7, 2026 is:

```text
2026.5.7-1
```

Python package metadata uses the PEP 440 equivalent:

```text
2026.5.7.post1
```

The app reports the public release version through:

```bash
dictate --version
```

Generate versions with:

```bash
python scripts/calver.py --date 2026-05-07 --sequence 1
python scripts/calver.py --date 2026-05-07 --sequence 1 --format pep440
```

Release tags and GitHub milestones should use the public version with a leading `v`, for example:

```text
v2026.5.7-1
```
