# Deploy

GitHub Actions runs the tests and builds the container image. It does not log in to GHCR and it does not push an image. Releases are built on loki.

## Release on loki

Image versions are `YY-MM.N`, such as `26-11.1`. The build number starts at 1 each month. `scripts/image-version` prints the version the next release would use.

On loki, from a clean `main` checkout:

```sh
git fetch origin --tags && git checkout main && git merge --ff-only origin/main && scripts/build-image
```

`scripts/build-image` stops if the worktree is dirty or the current branch is not `main`. Docker has to be running, and `~/.docker/config.json` has to contain a `ghcr.io` login. The login needs a GitHub token with `write:packages`. Pass the token on stdin. Do not put it on the command line and do not write it into the repo:

```sh
docker login ghcr.io --username <github-user> --password-stdin
```

`<github-user>` is the account that owns the token.

The script reads the next version from existing `YY-MM.N` tags, then builds and pushes `ghcr.io/mhjp-coder/fastprize:<version>` and `ghcr.io/mhjp-coder/fastprize:latest`. The build passes `APP_VERSION` so the image label `org.opencontainers.image.version` and `/app/VERSION` match the tag. It creates an annotated git tag, `Release <version>`, and pushes `HEAD` and that tag.

The image name comes from `git remote get-url origin`, lowercased, so this repository publishes `ghcr.io/mhjp-coder/fastprize`.

`:latest` only marks the most recent push. Production does not run it.

## Production

Production pins `IMAGE_TAG` to the numbered tag and runs that image:

```text
IMAGE_TAG=26-11.1
ghcr.io/mhjp-coder/fastprize:26-11.1
```

Do not set `IMAGE_TAG=latest`.

Compose selects the image with `FASTPRIZE_IMAGE`. Set it to `ghcr.io/mhjp-coder/fastprize:${IMAGE_TAG}`. Log Docker in to `ghcr.io` when the package is private, then:

```sh
docker compose pull
docker compose up -d --no-build
```

To roll back, set `IMAGE_TAG` to the previous `YY-MM.N` tag, point `FASTPRIZE_IMAGE` at `ghcr.io/mhjp-coder/fastprize:<that tag>`, and run the same pull and up.

## GitHub Actions

Pull requests and pushes to `main` run `uv run pytest`, `uv run ruff check src tests`, and a container build with `push: false`. The workflow permission is `contents: read`. Actions does not publish the image.
