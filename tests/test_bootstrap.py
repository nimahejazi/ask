import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from ask.config import Config

def test_bootstrap_system_prompt_creates_file_if_missing(tmp_path, monkeypatch):
    prompt_path = tmp_path / ".ask-sys-prompt"
    
    with monkeypatch.context() as m:
        m.setattr(Path, 'home', lambda: tmp_path)
        
        config = Config()
        config._set_path(tmp_path / ".askrc")
        
        with patch('ask.cli.Config', return_value=config):
            with patch('builtins.print'):
                from ask import cli
                result = config.get("system_prompt", "")
    
    assert not prompt_path.exists()

def test_bootstrap_system_prompt_preserves_existing_file(tmp_path, monkeypatch):
    prompt_path = tmp_path / ".ask-sys-prompt"
    existing_content = "# Existing custom prompt\nYou are a helpful assistant."
    
    prompt_path.write_text(existing_content)
    
    with monkeypatch.context() as m:
        m.setattr(Path, 'home', lambda: tmp_path)
        
        config = Config()
        config._set_path(tmp_path / ".askrc")
        
        with patch('ask.cli.Config', return_value=config):
            from ask import cli
            result = config.get("system_prompt", "")
    
    assert prompt_path.read_text() == existing_content
