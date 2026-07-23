# PyPI API Token

You need to create a PyPI API token and add it as a GitHub repository secret.

## Creating PyPI API Token

1. Log in to [PyPI](https://pypi.org/)
2. Go to [Account Settings → API Tokens](https://pypi.org/manage/account/)
3. Click "Create token"
4. Select "Project" scope and choose `nh-ask-cli`
5. Copy the generated token (starts with `pypi-...`)

## Adding Token to GitHub

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `PYPI_API_TOKEN`
5. Value: Paste your PyPI API token
6. Click **Add secret**

## Testing

After setup, create a test tag:

```bash
git tag v0.1.1-test
git push origin v0.1.1-test
```

This will trigger the workflow and publish `nh-ask-cli==0.1.1-test` to PyPI.

To clean up:
```bash
# Delete from PyPI (if needed, via web UI)
git tag -d v0.1.1-test
git push origin :refs/tags/v0.1.1-test
```

## After Naming Change

The package name is now `nh-ask-cli` on PyPI. All installation commands have been updated in this documentation.
