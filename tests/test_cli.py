import pytest
from unittest.mock import patch, MagicMock
from ask.cli import main, extract_command

def test_extract_command_with_code_block():
    text = "Here is the command:\n```bash\nls -la\n```"
    assert extract_command(text) == "ls -la"

def test_extract_command_without_code_block():
    text = "Just some text"
    assert extract_command(text) == "Just some text"

@patch('ask.cli.Config')
@patch('ask.cli.get_provider')
@patch('sys.argv', ['ask', 'hello'])
def test_main_conversational(mock_get_provider, mock_config):
    # Setup mocks
    config_instance = mock_config.return_value
    config_instance.exists.return_value = True
    config_instance.get.side_effect = lambda key, default=None: "mock" if key == "provider" else ""
    
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Hello AI!"
    mock_get_provider.return_value = mock_provider

    with patch('builtins.print') as mock_print:
        main()
        mock_print.assert_called_with("Hello AI!")

@patch('ask.cli.Config')
@patch('ask.cli.get_provider')
@patch('sys.argv', ['ask', '-c', 'hello'])
def test_main_command_mode(mock_get_provider, mock_config):
    # Setup mocks
    config_instance = mock_config.return_value
    config_instance.exists.return_value = True
    config_instance.get.side_effect = lambda key, default=None: "mock" if key == "provider" else ""
    
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Here is the command:\n```bash\necho hello\n```"
    mock_get_provider.return_value = mock_provider

    with patch('builtins.print') as mock_print:
        main()
        mock_print.assert_called_with("echo hello")

@patch('ask.cli.Config')
@patch('ask.cli.get_provider')
@patch('sys.argv', ['ask', 'hello'])
def test_main_system_prompt(mock_get_provider, mock_config):
    # Setup mocks
    config_instance = mock_config.return_value
    config_instance.exists.return_value = True
    def get_val(key, default=None):
        if key == "provider": return "mock"
        if key == "system_prompt": return "You are a bot."
        return default
    config_instance.get.side_effect = get_val
    
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Response"
    mock_get_provider.return_value = mock_provider

    main()
    mock_provider.chat.assert_called_with("hello", system_prompt="You are a bot.")
