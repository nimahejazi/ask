class Ask < Formula
  desc "AI CLI tool for natural language interaction with LLMs"
  homepage "https://github.com/anomalyco/ask"
  url "https://github.com/anomalyco/ask/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7ce2744a"
  license "MIT"

  depends_on "python@3.8" => :since

  def install
    system "pip3", "install", "-e", "."
  end

  test do
    system "ask", "--help"
  end
end
