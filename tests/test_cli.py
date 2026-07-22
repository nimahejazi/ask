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
    mock_provider.chat.return_value = {"content": "Hello AI!", "tool_calls": []}
    mock_get_provider.return_value = mock_provider

    with patch('ask.cli.console.print') as mock_rich_print:
        main()
        mock_rich_print.assert_called()

@patch('ask.cli.Config')
@patch('ask.cli.get_provider')
@patch('sys.argv', ['ask', '--it'])
@patch('builtins.input', side_effect=['hello', 'exit'])
def test_main_interactive_mode_with_tool_calls(mock_input, mock_get_provider, mock_config):
    # Setup mocks
    config_instance = mock_config.return_value
    config_instance.exists.return_value = True
    config_instance.get.side_effect = lambda key, default=None: "mock" if key == "provider" else ""
    
    def chat_side_effect(*args, **kwargs):
        history = kwargs.get("history", [])
        if not history:
            return {"content": "I'll execute a tool", "tool_calls": [
                {"name": "test_tool", "arguments": {"arg": "value"}}
            ]}
        else:
            return {"content": "Here is the result", "tool_calls": []}
    
    mock_provider = MagicMock()
    mock_provider.chat.side_effect = chat_side_effect
    mock_get_provider.return_value = mock_provider

    with patch('ask.cli.console.print') as mock_rich_print, \
         patch('ask.cli.execute_tool_calls') as mock_execute:
        mock_execute.return_value = ("success", "")
        main()
        assert mock_execute.called


@patch('ask.cli.Config')
@patch('ask.cli.get_provider')
@patch('sys.argv', ['ask', 'weather in Paris'])
def test_main_tool_synthesis_keeps_original_context(mock_get_provider, mock_config):
    config_instance = mock_config.return_value
    config_instance.exists.return_value = True
    config_instance.get.side_effect = lambda key, default=None: "mock" if key == "provider" else ""

    mock_provider = MagicMock()
    mock_provider.chat.side_effect = [
        {
            "content": "Checking the weather.",
            "tool_calls": [{"name": "get_weather", "arguments": {"city": "Paris"}}],
        },
        {"content": "It is sunny.", "tool_calls": []},
    ]
    mock_get_provider.return_value = mock_provider

    with patch('ask.cli.execute_tool_calls', return_value=('sunny', '')):
        main()

    mock_provider.chat.assert_any_call(
        "Tool execution results:\nsunny",
        system_prompt="",
        history=[
            {"role": "user", "content": "weather in Paris"},
            {"role": "assistant", "content": "Checking the weather."},
        ],
        tools=[],
    )


@patch('ask.cli.Config')
@patch('ask.cli.get_provider')
@patch('sys.argv', ['ask', '-c', 'hello'])
def test_main_command_mode(mock_get_provider, mock_config):
    # Setup mocks
    config_instance = mock_config.return_value
    config_instance.exists.return_value = True
    config_instance.get.side_effect = lambda key, default=None: "mock" if key == "provider" else ""
    
    mock_provider = MagicMock()
    mock_provider.chat.return_value = {"content": "Here is the command:\n```bash\necho hello\n```", "tool_calls": []}
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
    mock_provider.chat.return_value = {"content": "Response", "tool_calls": []}
    mock_get_provider.return_value = mock_provider

    main()
    mock_provider.chat.assert_called_with("hello", system_prompt="You are a bot.", tools=[])

@patch('ask.cli.Config')
@patch('ask.cli.get_provider')
@patch('sys.argv', ['ask', '--it'])
@patch('builtins.input', side_effect=['hello', 'how are you?', 'exit'])
def test_main_interactive_mode(mock_input, mock_get_provider, mock_config):
    # Setup mocks
    config_instance = mock_config.return_value
    config_instance.exists.return_value = True
    config_instance.get.side_effect = lambda key, default=None: "mock" if key == "provider" else ""
    
    mock_provider = MagicMock()
    mock_provider.chat.return_value = {"content": "AI Response", "tool_calls": []}
    mock_get_provider.return_value = mock_provider

    with patch('ask.cli.console.print') as mock_rich_print:
        main()
        # Should call chat twice for 'hello' and 'how are you?'
        assert mock_provider.chat.call_count == 2
        
        # First call should have no history
        mock_provider.chat.assert_any_call("hello", system_prompt="", history=[], tools=[])
        
        # Second call should have first turn in history
        mock_provider.chat.assert_any_call(
            "how are you?", 
            system_prompt="", 
            history=[
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "AI Response"}
            ],
            tools=[]
        )

@patch('ask.cli.Config')
@patch('ask.cli.get_provider')
@patch('sys.argv', ['ask', 'initial query', '--it'])
@patch('builtins.input', side_effect=['follow up', 'exit'])
def test_main_interactive_mode_with_initial_query(mock_input, mock_get_provider, mock_config):
    # Setup mocks
    config_instance = mock_config.return_value
    config_instance.exists.return_value = True
    config_instance.get.side_effect = lambda key, default=None: "mock" if key == "provider" else ""
    
    mock_provider = MagicMock()
    mock_provider.chat.return_value = {"content": "AI Response", "tool_calls": []}
    mock_get_provider.return_value = mock_provider

    with patch('ask.cli.console.print') as mock_rich_print:
        main()
        assert mock_provider.chat.call_count == 2
        mock_provider.chat.assert_any_call("initial query", system_prompt="", history=[], tools=[])
        mock_provider.chat.assert_any_call(
            "follow up", 
            system_prompt="", 
            history=[
                {"role": "user", "content": "initial query"},
                {"role": "assistant", "content": "AI Response"}
            ],
            tools=[]
        )
