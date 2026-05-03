# NoETL APT Repository

This repository hosts the Debian/Ubuntu APT index for the maintained NoETL
Rust CLI.

Source repository:

```text
https://github.com/noetl/cli
```

## Install

```bash
echo 'deb [trusted=yes] https://noetl.github.io/apt jammy main' | sudo tee /etc/apt/sources.list.d/noetl.list
sudo apt-get update
sudo apt-get install noetl
noetl --version
```

Use `noble` instead of `jammy` on Ubuntu 24.04.

## Current Index

- Package: `noetl`
- CLI source: `noetl/cli`
- Indexed version: `2.13.0-1`
- Indexed architecture: `amd64`

The current `v2.13.0` CLI release does not publish an arm64 Debian artifact.
Do not index older arm64 packages as current. Add arm64 back to the APT
metadata only after `noetl/cli` publishes a matching arm64 `.deb` for the same
CLI version.
