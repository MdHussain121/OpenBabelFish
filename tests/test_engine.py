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
