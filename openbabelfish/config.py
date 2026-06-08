import json
import os
from pathlib import Path

def get_openbabelfish_home() -> Path:
    """
    Resolve the OpenBabelFish home directory with a priority on local portability:
    1. OPENBABELFISH_HOME environment variable
    2. Current Working Directory (if it looks like an OpenBabelFish project root)
    3. Project Root (parent of the package directory)
    4. User home directory ~/.openbabelfish (Default fallback)
    """
    # 1. Environment Variable Override
    env_home = os.environ.get("OPENBABELFISH_HOME")
    if env_home:
        return Path(env_home).absolute()

    # 2. Portable/Local Detection (CWD)
    # If run from the root of the repo, prefer local storage
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists() or (cwd / "openbabelfish").exists() or (cwd / "models").exists():
        return cwd.absolute()

    # 3. Project-relative Detection (Package Parent)
    package_root = Path(__file__).parent.parent
    if (package_root / "pyproject.toml").exists() or (package_root / "models").exists():
        return package_root.absolute()

    # 4. Standard User Directory Fallback
    user_home = Path.home() / ".openbabelfish"
    return user_home.absolute()

# Resolved Paths
BASE_DIR = get_openbabelfish_home()
CONFIG_FILE = BASE_DIR / "config.json"
MODELS_DIR = BASE_DIR / "models"

DEFAULT_CONFIG = {
    "model_variant": None,
    "model_path": None,
    "device": "cpu",
    "quantization": "int8",
    "ocr_device": "cpu"
}

def load_config():
    """
    Load configuration with Environment Variable overrides (Twelve-Factor Factor III).
    Search Order: Env Var > config.json > Default
    """
    config = DEFAULT_CONFIG.copy()

    # Load from file if exists
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception:
            pass
    
    # Environment Variable Overrides (Twelve-Factor: Config in Environment)
    for key in config.keys():
        env_key = f"OPENBABELFISH_{key.upper()}"
        env_val = os.environ.get(env_key)
        if env_val:
            config[key] = env_val

    # Aliases
    model_override = os.environ.get("OPENBABELFISH_MODEL")
    if model_override:
        config["model_variant"] = model_override

    # Dynamic Path Resolution (Ensures portability across environments)
    if config.get("model_variant"):
        config["model_path"] = str(get_model_path(config["model_variant"]))

    return config

def save_config(config):
    """Save configuration to the resolved home directory (excluding ephemeral paths)."""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(exist_ok=True)
    
    # Don't save dynamic/absolute paths to the config file to keep it portable
    save_data = config.copy()
    if "model_path" in save_data:
        del save_data["model_path"]
        
    with open(CONFIG_FILE, "w") as f:
        json.dump(save_data, f, indent=4)

def get_model_path(variant=None):
    """Get the path to the model relative to the resolved home."""
    if not variant:
        config = load_config()
        variant = config.get("model_variant")
    
    if not variant:
        return None
        
    return MODELS_DIR / f"nllb-200-{variant}"

def is_setup_complete():
    """Check if the model and configuration are valid in the current home."""
    config = load_config()
    variant = config.get("model_variant")
    if not variant:
        return False
    
    path = get_model_path(variant)
    return path.exists() and (path / "model.bin").exists()
