# Releasing

Releases are published to PyPI by GitHub Actions when a GitHub Release is published.

## One-time PyPI setup

Configure PyPI Trusted Publishing for the `donotreadagain` project:

- Owner: `melodysdreamj`
- Repository name: `donotreadagain`
- Workflow name: `publish.yml`
- Environment name: `pypi`

No PyPI API token is needed for the workflow. If you previously created one, prefer revoking it
after Trusted Publishing is working.

## Release steps

1. Update `pyproject.toml` to the new version.
2. Move the matching `CHANGELOG.md` notes under that version.
3. Run tests locally:

   ```bash
   .venv/bin/python -m pytest -q
   ```

4. Commit and push to `main`.
5. Create and publish a GitHub Release with a tag matching the version, for example `v0.1.2`.

Publishing the GitHub Release triggers `.github/workflows/publish.yml`, which tests the package,
builds the source distribution and wheel, checks metadata, and publishes the artifacts to PyPI.
