class NhAskCli < Formula
  desc "AI CLI tool for natural language interaction with LLMs"
  homepage "https://github.com/nimahejazi/ask"
  url "https://github.com/nimahejazi/ask/archive/refs/tags/v0.2.12.tar.gz"
  sha256 "0019dfc4b32d63c1392aa264aed2253c1e0c2fb09216f8e2cc269bbfb8bb49b5"
  license "MIT"

  depends_on "python"

  def install
    system "pip3", "install", "-e", "."
  end

  test do
    system "ask", "--help"
  end
end
