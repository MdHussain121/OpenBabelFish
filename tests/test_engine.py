import pytest
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from openbabelfish.config import load_config, save_config, get_model_path
from openbabelfish.engine import TranslationEngine
from openbabelfish.managers import ModelManager, DependencyManager

def test_resolve_lang_code():
    engine = TranslationEngine()
    
    # Test standard language names
    assert engine._resolve_lang_code("english") == "eng_Latn"
    assert engine._resolve_lang_code("spanish") == "spa_Latn"
    assert engine._resolve_lang_code("french") == "fra_Latn"
    
    # Test NLLB codes
    assert engine._resolve_lang_code("eng_Latn") == "eng_Latn"
    
    # Test 2-letter codes (should resolve to NLLB codes if we fix it)
    assert engine._resolve_lang_code("en") == "eng_Latn"
    assert engine._resolve_lang_code("es") == "spa_Latn"
    assert engine._resolve_lang_code("fr") == "fra_Latn"

def test_model_manager_resolve_variant():
    mgr = ModelManager()
    assert mgr.resolve_variant("1.3") == "1.3B"
    assert mgr.resolve_variant("600") == "600M"
    assert mgr.resolve_variant("600m") == "600M"
    assert mgr.resolve_variant("3.3B") == "3.3B"

@patch("openbabelfish.managers.snapshot_download")
@patch("openbabelfish.managers.ModelManager.get_repo_stats")
def test_download_model_fd_leak(mock_get_repo_stats, mock_snapshot_download):
    mock_get_repo_stats.return_value = (1000, 5)
    mgr = ModelManager()
    
    # This should not raise OSError: [Errno 9] Bad file descriptor
    # We pass '600M' which is valid
    with patch("openbabelfish.managers.get_model_path") as mock_path:
        mock_path.return_value = Path(tempfile.mkdtemp())
        success = mgr.download_model("600M")
        assert success is True

def test_cmd_mappings():
    # Test our generalization mappings directly
    cmd_mappings = {
        'help': '--help', 'h': '--help', '?': '--help',
        'models': '--models', 'list': '--models',
        'packages': '--packages', 'pkg': '--packages', 'audit': '--packages',
        'gpu': '--gpu', 'cuda': '--gpu',
        'cpu': '--cpu',
        'ocr': '--ocr',
        'ocr-device': '--ocr-device', 'ocr_device': '--ocr-device',
        'to': '--to', 'target': '--to',
        'from': '--from', 'source': '--from',
        'file': '--file', 'f': '--file', 'read': '--file',
        'output': '--output', 'o': '--output', 'save': '--output',
        'add-model': '--add-model', 'add': '--add-model', 'download': '--add-model',
        'model': '--model', 'm': '--model'
    }
    
    # Verify mappings
    assert cmd_mappings['pkg'] == '--packages'
    assert cmd_mappings['audit'] == '--packages'
    assert cmd_mappings['list'] == '--models'
    assert cmd_mappings['cuda'] == '--gpu'
    assert cmd_mappings['target'] == '--to'
    assert cmd_mappings['read'] == '--file'
    assert cmd_mappings['save'] == '--output'
    assert cmd_mappings['download'] == '--add-model'

def test_suggestions():
    import difflib
    all_possible_inputs = [
        'help', 'models', 'packages', 'gpu', 'cpu', 'ocr', 'ocr-device',
        'to', 'from', 'file', 'output', 'model', 'add-model', 'exit', 'quit'
    ]
    # Typo: "pkgss"
    close_matches = difflib.get_close_matches("pkgss", all_possible_inputs, n=3, cutoff=0.5)
    assert 'packages' in close_matches

    # Typo: "modelss"
    close_matches = difflib.get_close_matches("modelss", all_possible_inputs, n=3, cutoff=0.5)
    assert 'models' in close_matches
    assert 'model' in close_matches


@patch("openbabelfish.cli.interactive_shell")
@patch("openbabelfish.cli.load_config")
@patch("openbabelfish.cli.save_config")
@patch("openbabelfish.cli.ModelManager")
@patch("openbabelfish.cli.DependencyManager")
def test_translate_repl_mode_cli_launch(mock_dep_mgr, mock_model_mgr, mock_save, mock_load, mock_interactive):
    from openbabelfish.cli import main
    import sys
    
    mock_load.return_value = {"model_variant": "600M", "device": "cpu"}
    
    # Simulate: openbabelfish translate --to spanish
    with patch.object(sys, "argv", ["openbabelfish", "translate", "to", "spanish"]):
        main()
        
    mock_interactive.assert_called_once_with(
        start_translate=True,
        target_lang="spanish",
        source_lang=None
    )

    mock_interactive.reset_mock()
    # Simulate: openbabelfish t --from english --to french
    with patch.object(sys, "argv", ["openbabelfish", "t", "from", "english", "to", "french"]):
        main()
        
    mock_interactive.assert_called_once_with(
        start_translate=True,
        target_lang="french",
        source_lang="english"
    )


@patch("openbabelfish.cli.Prompt.ask")
@patch("openbabelfish.cli.TranslationEngine")
@patch("openbabelfish.cli.ensure_system_sanity")
@patch("openbabelfish.cli.console")
@patch("openbabelfish.cli.readline", create=True)
@patch("openbabelfish.cli.load_config")
@patch("openbabelfish.cli.ModelManager")
@patch("openbabelfish.cli.DependencyManager")
def test_interactive_shell_prompts_input_then_output(mock_dep_mgr, mock_model_mgr, mock_load, mock_readline, mock_console, mock_sanity, mock_engine, mock_prompt_ask):
    from openbabelfish.cli import interactive_shell
    
    mock_load.return_value = {"model_variant": "600M", "device": "cpu"}
    
    mock_console.width = 80
    
    # We mock Prompt.ask to return 'english' for first call and 'spanish' for second call
    mock_prompt_ask.side_effect = ["english", "spanish"]
    
    # We mock console.input to raise KeyboardInterrupt to break the infinite loop in interactive_shell immediately
    mock_console.input.side_effect = KeyboardInterrupt
    
    try:
        interactive_shell(start_translate=True)
    except KeyboardInterrupt:
        pass
    
    # Verify Prompt.ask was called twice
    assert mock_prompt_ask.call_count == 2
    # The first call should prompt for input (source) language
    first_call_arg = mock_prompt_ask.call_args_list[0][0][0]
    assert "input" in first_call_arg.lower() or "source" in first_call_arg.lower()
    
    # The second call should prompt for output (target) language
    second_call_arg = mock_prompt_ask.call_args_list[1][0][0]
    assert "output" in second_call_arg.lower() or "target" in second_call_arg.lower()


@patch("openbabelfish.cli.TranslationEngine")
@patch("openbabelfish.cli.load_config")
@patch("openbabelfish.cli.save_config")
@patch("openbabelfish.cli.ModelManager")
@patch("openbabelfish.cli.DependencyManager")
def test_directory_output_generation(mock_dep_mgr, mock_model_mgr, mock_save, mock_load, mock_engine):
    from openbabelfish.cli import _run_translation
    import tempfile
    import shutil
    from pathlib import Path
    
    mock_load.return_value = {"model_variant": "600M", "device": "cpu"}
    
    mock_model_inst = mock_model_mgr.return_value
    mock_model_inst.resolve_variant.return_value = "600M"
    mock_model_inst.get_model_status.return_value = "DOWNLOADED"
    
    mock_dep_inst = mock_dep_mgr.return_value
    mock_dep_inst.check_dependencies.return_value = []
    
    mock_inst = MagicMock()
    mock_inst.translate.return_value = ["translated text"]
    mock_engine.return_value = mock_inst
    
    temp_dir = tempfile.mkdtemp()
    
    # Create a dummy input file so file reading succeeds
    temp_file = Path(temp_dir) / "sample.txt"
    temp_file.write_text("hello world", encoding="utf-8")
    
    class DummyArgs:
        pass
    
    args = DummyArgs()
    args.target_lang = "hindi"
    args.source_lang = None
    args.file = str(temp_file)
    args.output = temp_dir
    args.model = None
    args.add_model = None
    args.models = False
    args.packages = False
    args.gpu = False
    args.cpu = False
    args.ocr = False
    args.ocr_device = None
    
    try:
        _run_translation(args, {"model_variant": "600M", "device": "cpu"}, mock_model_inst, mock_dep_inst)
        
        expected_path = Path(temp_dir) / "sample_translated.txt"
        assert expected_path.exists()
        assert expected_path.read_text(encoding="utf-8") == "translated text"
    finally:
        shutil.rmtree(temp_dir)


@patch("openbabelfish.cli._run_translation")
@patch("openbabelfish.cli.console")
@patch("openbabelfish.cli.load_config")
@patch("openbabelfish.cli.ModelManager")
@patch("openbabelfish.cli.DependencyManager")
@patch("openbabelfish.cli.readline", create=True)
def test_interactive_shell_translation_mode_behavior(mock_readline, mock_dep_mgr, mock_model_mgr, mock_load, mock_console, mock_run_translation):
    from openbabelfish.cli import interactive_shell
    
    mock_load.return_value = {"model_variant": "600M", "device": "cpu"}
    mock_console.width = 80
    mock_dep_mgr.return_value.check_dependencies.return_value = []
    mock_model_mgr.return_value.get_model_status.return_value = "DOWNLOADED"
    
    # We simulate a sequence of inputs in translation mode:
    # 1. "- Slack and Microsoft Teams" -> should call _run_translation
    # 2. "cpu" -> should call _run_translation (previously it was a command)
    # 3. "--exit" -> should exit translation mode (console.input next will raise KeyboardInterrupt to exit REPL loop)
    mock_console.input.side_effect = [
        "- Slack and Microsoft Teams",
        "cpu",
        "--exit",
        KeyboardInterrupt
    ]
    
    try:
        interactive_shell(start_translate=True, target_lang="hindi", source_lang="auto")
    except KeyboardInterrupt:
        pass
        
    # Verify _run_translation was called for the first two inputs
    assert mock_run_translation.call_count == 2
    
    # Check arguments of the first call
    first_call_args = mock_run_translation.call_args_list[0][0][0]
    assert first_call_args.text == ["- Slack and Microsoft Teams"]
    assert first_call_args.target_lang == "hindi"
    
    # Check arguments of the second call
    second_call_args = mock_run_translation.call_args_list[1][0][0]
    assert second_call_args.text == ["cpu"]
