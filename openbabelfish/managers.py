import os
import sys
import subprocess
import importlib
import contextlib
import io
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, 
    DownloadColumn, TransferSpeedColumn, TimeRemainingColumn, TimeElapsedColumn
)
from huggingface_hub import snapshot_download, HfApi
from huggingface_hub.utils import disable_progress_bars, enable_progress_bars
import huggingface_hub.utils.logging as hf_logging

# Silence all HF noise globally at the module level
hf_logging.set_verbosity_error()

from .config import get_model_path, load_config

console = Console()

# Registry of optimized CTranslate2 models
MODEL_VARIANTS = {
    "600M": "JustFrederik/nllb-200-distilled-600M-ct2-int8",
    "1.3B": "OpenNMT/nllb-200-distilled-1.3B-ct2-int8",
    "3.3B": "OpenNMT/nllb-200-3.3B-ct2-int8"
}

VARIANT_INFO = {
    "600M": "~2.4 GB - Fast, low RAM (Recommended for CPU)",
    "1.3B": "~5.4 GB - Balanced quality and speed",
    "3.3B": "~13 GB - High quality, requires lots of RAM"
}

# Comprehensive dependencies grouped by functional area
REQUIRED_PACKAGES = {
    "Core Module (Required)": {
        "ctranslate2": ">=4.0",
        "transformers": ">=4.40.0",
        "sentencepiece": ">=0.2.0",
        "langid": ">=1.1",
        "huggingface_hub": ">=0.22",
        "numpy": "<2.0.0",
        "rich": ">=13.0",
        "click": ">=8.1",
        "python-dotenv": ">=1.0",
        "urllib3": "<2.0.0"
    },
    "GPU Acceleration (Optional)": {
        "torch": ">=2.0",
        "nvidia-cublas-cu12": ">=12.0",
        "nvidia-cudnn-cu12": ">=8.0"
    },
    "Utility (Optional)": {
        "Pillow": ">=9.0.0"
    }
}

class DependencyManager:
    """Manages external libraries and dynamic pip installations."""
    
    @staticmethod
    def is_gpu_installed() -> bool:
        """Check if CUDA runtime libraries are installed in the environment."""
        try:
            # Check for package metadata instead of imports, which is more reliable
            import importlib.metadata
            importlib.metadata.version("nvidia-cublas-cu12")
            return True
        except importlib.metadata.PackageNotFoundError:
            return False

    def check_dependencies(self) -> List[dict]:
        """Audit the current environment for all relevant packages."""
        import importlib.metadata
        results = []
        for category, packages in REQUIRED_PACKAGES.items():
            for pkg, req in packages.items():
                try:
                    version = importlib.metadata.version(pkg)
                    status = "installed"
                    # Version mismatch checks
                    if pkg == "numpy" and version.startswith("2."):
                         status = "mismatch"
                    elif pkg == "urllib3" and version.startswith("2."):
                         status = "mismatch"
                except importlib.metadata.PackageNotFoundError:
                    version = "Not found"
                    status = "missing"
                
                results.append({
                    "group": category,
                    "package": pkg,
                    "required": req,
                    "installed": version,
                    "status": status
                })
        return results

    def install_missing(self, packages: List[str]):
        """Install specific missing packages via pip."""
        if not packages:
            return True
            
        console.print(f"\n[bold cyan]Installing required packages: {', '.join(packages)}...[/]")
        try:
            with console.status("[bold green]Pip is updating your environment...[/]"):
                to_install = []
                # Flatten the requirements for lookup
                lookup = {}
                for cat in REQUIRED_PACKAGES.values():
                    lookup.update(cat)

                for p in packages:
                    if p in lookup:
                        to_install.append(f"{p}{lookup[p]}")
                    else:
                        to_install.append(p)
                
                subprocess.check_call([sys.executable, "-m", "pip", "install", *to_install])
            console.print("[bold green]✓ Packages installed successfully![/]")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]✗ Failed to install packages:[/] {e}")
            return False

    @staticmethod
    def install_gpu_support():
        """Install NVIDIA CUDA runtime libraries via pip subprocess."""
        console.print("\n[bold cyan]Installing NVIDIA GPU support...[/]")
        console.print("[dim]Downloading ~1.2 GB of CUDA 12 runtimes. This only happens once.[/dim]\n")
        
        try:
            # We use -q for quiet but show a spinner
            with console.status("[bold green]Pip is downloading CUDA kernels...[/]"):
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", "-q",
                    "nvidia-cublas-cu12", "nvidia-cudnn-cu12"
                ])
            console.print("[bold green]✓ GPU dependencies installed successfully![/]")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]✗ Failed to install GPU support:[/] {e}")
            return False

class ModelManager:
    """Manages local model storage and Hugging Face downloads."""
    
    @staticmethod
    def get_available_variants() -> Dict[str, str]:
        return MODEL_VARIANTS

    @staticmethod
    def resolve_variant(name: str) -> str:
        """Resolve shorthand (1.3, 600) or case-insensitive names to canonical variant."""
        if not name:
            return None
        
        name_upper = name.upper()
        # Direct Match
        if name_upper in MODEL_VARIANTS:
            return name_upper
            
        # Shorthand Match (e.g. 1.3 -> 1.3B, 600 -> 600M)
        for v in MODEL_VARIANTS:
            # Check if name is a prefix or numeric part
            variant_numeric = "".join(filter(lambda c: c.isdigit() or c == ".", v))
            input_numeric = "".join(filter(lambda c: c.isdigit() or c == ".", name))
            
            if name_upper == variant_numeric or input_numeric == variant_numeric:
                return v
                
        return name_upper # Fallback to upper

    @staticmethod
    def get_model_status(variant: str) -> str:
        """Categorize the download state of a variant."""
        path = get_model_path(variant)
        if not path or not path.exists():
            return "MISSING"
        
        # Check for the critical weight file
        if (path / "model.bin").exists():
            return "DOWNLOADED"
            
        return "INCOMPLETE"

    @staticmethod
    def get_installed_models() -> List[str]:
        """List variant names that are already fully downloaded."""
        installed = []
        for name in MODEL_VARIANTS:
            if ModelManager.get_model_status(name) == "DOWNLOADED":
                installed.append(name)
        return installed

    @staticmethod
    def get_repo_stats(repo_id: str) -> tuple:
        """Fetch total repository size and file count from Hugging Face API."""
        try:
            api = HfApi()
            info = api.model_info(repo_id, files_metadata=True)
            total_size = sum(s.size for s in info.siblings if s.size is not None)
            file_count = len(info.siblings)
            return total_size, file_count
        except Exception:
            return None, 0

    def download_model(self, variant: str):
        """Download a model variant with a high-fidelity progress bar."""
        variant = variant.upper()
        if variant not in MODEL_VARIANTS:
            raise ValueError(f"Unknown variant: {variant}")
            
        repo_id = MODEL_VARIANTS[variant]
        local_dir = get_model_path(variant)
        
        console.print(f"\n[bold]Model Download: {variant}[/]")
        console.print(f"[dim]Repository: {repo_id}[/dim]\n")
        
        total_size, file_count = self.get_repo_stats(repo_id)
        
        # Record original file descriptors (OS level)
        try:
            old_stdout_fd = sys.stdout.fileno()
            old_stderr_fd = sys.stderr.fileno()
        except (AttributeError, io.UnsupportedOperation):
            # Fallback for environments where fileno() isn't available
            return self._download_fallback(variant, repo_id, local_dir, total_size)

        # Duplicate the terminal's FD so we have a private "Clean Channel"
        saved_stdout_fd = os.dup(old_stdout_fd)
        
        try:
            # SHADOW CONSOLE: Absolute silence for all library noise
            with open(os.devnull, "w") as fnull:
                null_fd = fnull.fileno()
                os.dup2(null_fd, old_stdout_fd)
                os.dup2(null_fd, old_stderr_fd)
                
                with os.fdopen(saved_stdout_fd, "w") as private_out:
                    local_console = Console(file=private_out)
                    
                    if file_count > 0:
                        local_console.print(f"Fetching {file_count} files")

                    with Progress(
                        SpinnerColumn(spinner_name="dots"),
                        TextColumn(f"[bold cyan]Downloading {variant}... [/]"),
                        TimeElapsedColumn(),
                        console=local_console,
                    ) as progress:
                        progress.add_task("download", total=None)
                        
                        # Run the download in silent mode
                        disable_progress_bars()
                        try:
                            snapshot_download(
                                repo_id=repo_id,
                                local_dir=local_dir,
                            )
                        finally:
                            enable_progress_bars()
                
            # Success - terminal fds will be restored in finally
            return True
        except Exception as e:
            # We must restore terminal output if it crashed inside the muzzle
            os.dup2(saved_stdout_fd, old_stdout_fd) 
            console.print(f"[bold red]✗ Download error:[/] {e}")
            return False
        finally:
            # Restore the system FDs 1 and 2 to their original terminal state
            os.dup2(saved_stdout_fd, old_stdout_fd)
            # We don't have a saved stderr fd handy so we just use the stdout one 
            # as a reasonable proxy to get the terminal back to normal
            os.dup2(saved_stdout_fd, old_stderr_fd)
            os.close(saved_stdout_fd)

    def _download_fallback(self, variant, repo_id, local_dir, total_size):
        """Simple download without redirection if OS-level hooks fail."""
        try:
            with Progress(
                SpinnerColumn(spinner_name="dots"),
                TextColumn("[bold cyan]Fetching {variant}…"),
                BarColumn(bar_width=40),
                expand=False,
            ) as progress:
                task = progress.add_task("Downloading", total=total_size)
                disable_progress_bars()
                try:
                    snapshot_download(repo_id=repo_id, local_dir=local_dir)
                finally:
                    enable_progress_bars()
            return True
        except Exception as e:
            console.print(f"[bold red]✗ Fallback download error:[/] {e}")
            return False
