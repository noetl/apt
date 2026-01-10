# NoETL APT Repository

Official Debian/Ubuntu package repository for NoETL.

## Installation

Add the repository and install NoETL:

```bash
# Add NoETL repository
echo 'deb [trusted=yes] https://noetl.github.io/apt jammy main' | sudo tee /etc/apt/sources.list.d/noetl.list

# Update package list
sudo apt-get update

# Install NoETL
sudo apt-get install noetl
```

## Supported Distributions

- Ubuntu 22.04 (Jammy)
- Ubuntu 20.04 (Focal)
- Ubuntu 24.04 (Noble)
- Debian-based distributions

## Verify Installation

```bash
noetl --version
```

## Documentation

Visit [noetl.dev](https://noetl.dev) for complete documentation.
