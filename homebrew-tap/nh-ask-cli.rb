class NhAskCli < Formula
  desc "AI CLI tool for natural language interaction with LLMs"
  homepage "https://github.com/nimahejazi/ask"
  url "https://github.com/nimahejazi/ask/archive/refs/tags/v0.2.12.tar.gz"
  sha256 "738cfc99eaadcbf7d2bb0b523903ac8cc0b4e776362a339669af7c9908e8e980"
  license "MIT"

  depends_on "python@3.12"

  def install
    system Formula["python@3.12"].opt_bin/"python3.12", "-m", "pip", "install",
           *std_pip_args, "."
  end

  test do
    system "#{bin}/ask", "--help"
  end
end