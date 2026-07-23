class NhAskCli < Formula
  desc "AI CLI tool for natural language interaction with LLMs"
  homepage "https://github.com/nimahejazi/ask"
  url "https://github.com/nimahejazi/ask/archive/refs/tags/v0.2.12.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"

  depends_on "python"

  def install
    system "pip3", "install", "-e", "."
  end

  test do
    system "ask", "--help"
  end
end
