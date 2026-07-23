# Homebrew Tap for nh-ask-cli

This repository contains the Homebrew formula for `nh-ask-cli`.

## Installation

Add the tap and install:

```bash
brew install nimahejazi/tap/nh-ask-cli
brew update
brew upgrade nh-ask-cli
```

## Manual Formula Update Process

When a new version is released to PyPI, follow these steps to update the formula:

### 1. Create a release tarball

```bash
git archive --format tar.gz --output nh-ask-cli-vX.Y.Z.tar.gz vX.Y.Z
```

Replace `X.Y.Z` with the actual version number.

### 2. Generate SHA256 checksum

```bash
sha256sum nh-ask-cli-vX.Y.Z.tar.gz
```

Copy the hash output.

### 3. Update the formula

Edit `nh-ask-cli.rb` and update:

- `url` - Change version from old to new (e.g., `v0.1.0` → `v0.2.0`)
- `sha256` - Replace placeholder with the new SHA256 hash

Example:
```ruby
class NhAskCli < Formula
  desc "AI CLI tool for natural language interaction with LLMs"
  homepage "https://github.com/nimahejazi/ask"
  url "https://github.com/nimahejazi/ask/archive/refs/tags/v0.2.0.tar.gz"
  sha256 "actual-sha256-hash-here"  # Replace this line
  license "MIT"

  depends_on "python@3.8" => :since

  def install
    system "pip3", "install", "-e", "."
  end

  test do
    system "ask", "--help"
  end
end
```

### 4. Commit and push

```bash
git add nh-ask-cli.rb
git commit -m "Update nh-ask-cli formula to vX.Y.Z"
git push origin main
```

---

## Automated Release Flow

The automated GitHub Actions workflow (`.github/workflows/release.yml`) publishes new versions to PyPI automatically when tags are created. After the PyPI publish succeeds, manually update this Homebrew formula following the steps above.
