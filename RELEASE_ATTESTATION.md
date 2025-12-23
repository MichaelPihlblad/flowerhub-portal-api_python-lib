# PyPI Release Attestations

This project uses PyPI's attestation feature to provide cryptographic proof of provenance for all published packages.

## What are PyPI Attestations?

PyPI attestations (also called "artifact attestations" or "provenance") provide verifiable evidence about:
- **What** was built (the exact package artifacts)
- **Where** it was built (GitHub Actions workflow)
- **Who** authorized the build (via OIDC identity token)

This enhances supply chain security by allowing users to verify that packages came from the legitimate source repository.

## How It Works

1. **GitHub Actions Workflow**: When a release is published, the `release.yml` workflow is triggered
2. **Build**: The package is built using Python's `build` tool
3. **Attestation**: GitHub generates cryptographic attestations linking the artifacts to the workflow
4. **Publishing**: The `pypa/gh-action-pypi-publish` action uploads both the package and its attestations to PyPI
5. **Verification**: Users can verify the attestations using PyPI's UI or the `pip` command

## PyPI Configuration Required

To enable attestations, the PyPI project must be configured with **Trusted Publishing**:

1. Go to the project settings on PyPI: https://pypi.org/manage/project/flowerhub-portal-api-client/settings/publishing/
2. Add a new "Trusted Publisher"
3. Configure with:
   - **PyPI Project Name**: `flowerhub-portal-api-client`
   - **Owner**: `MichaelPihlblad`
   - **Repository name**: `flowerhub-portal-api_python-lib`
   - **Workflow name**: `release.yml`
   - **Environment name**: (leave empty if not using environments)

Once configured, the workflow will automatically authenticate with PyPI using OIDC tokens instead of API tokens, and attestations will be generated and uploaded automatically.

## Benefits

- **No API tokens needed**: Uses OIDC for secure, keyless authentication
- **Cryptographic proof**: Users can verify packages haven't been tampered with
- **Transparency**: Clear audit trail of what was built and deployed
- **Supply chain security**: Meets modern security best practices

## Verifying Attestations

Users can verify package attestations in several ways:

1. **PyPI Web UI**: View attestations on the package's PyPI page
2. **pip**: Future versions of pip will support automatic verification
3. **sigstore**: Use the `sigstore-python` tool to manually verify attestations

## References

- [PEP 740 - Index support for digital attestations](https://peps.python.org/pep-0740/)
- [PyPI Trusted Publishing documentation](https://docs.pypi.org/trusted-publishers/)
- [GitHub Actions OIDC documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
