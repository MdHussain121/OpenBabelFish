import logging
import os
import re
import sys
import subprocess
import contextlib
import io
import importlib.metadata
from pathlib import Path
from typing import Dict, List, Tuple

from packaging.version import Version

from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
)
from huggingface_hub import snapshot_download, HfApi
from huggingface_hub.utils import disable_progress_bars, enable_progress_bars
import huggingface_hub.utils.logging as hf_logging

# Silence all HF noise globally at the module level
hf_logging.set_verbosity_error()

from .config import get_model_path

console = Console()
logger = logging.getLogger(__name__)

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
    "Document Extraction (Auto-installed)": {
        "PyMuPDF": ">=1.24.0",
        "python-docx": ">=1.0.0",
        "python-pptx": ">=0.6.21",
        "EbookLib": ">=0.18",
        "beautifulsoup4": ">=4.12.0"
    },
    "OCR Engine (Auto-installed)": {
        "easyocr": ">=1.7"
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
            importlib.metadata.version("nvidia-cublas-cu12")
            return True
        except importlib.metadata.PackageNotFoundError:
            return False

    @staticmethod
    def _matches_specifier(installed_version: str, specifier: str) -> bool:
        """Check whether an installed version satisfies a version specifier like '>=4.0' or '<2.0.0'."""
        try:
            ver = Version(installed_version)
            # Parse operator and target from specifier
            m = re.match(r'([><=!]+)(.*)', specifier.strip())
            if not m:
                return True  # No specifier to check
            op, target_str = m.group(1), m.group(2).strip()
            target = Version(target_str)
            ops = {
                ">=": ver >= target,
                "<=": ver <= target,
                ">": ver > target,
                "<": ver < target,
                "==": ver == target,
                "!=": ver != target,
            }
            return ops.get(op, True)
        except Exception:
            return True  # If parsing fails, assume OK

    def check_dependencies(self) -> List[dict]:
        """Audit the current environment for all relevant packages."""
        results = []
        for category, packages in REQUIRED_PACKAGES.items():
            for pkg, req in packages.items():
                try:
                    version = importlib.metadata.version(pkg)
                    # Use proper version comparison against the specifier
                    if self._matches_specifier(version, req):
                        status = "installed"
                    else:
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

    def install_missing(self, packages: List[str]) -> bool:
        """Install specific missing packages via pip."""
        if not packages:
            return True

        # Only allow packages from the known registry
        known: Dict[str, str] = {}
        for cat in REQUIRED_PACKAGES.values():
            known.update(cat)
        unknown = [p for p in packages if p not in known]
        if unknown:
            console.print(f"[bold red]✗ Unknown packages refused: {', '.join(unknown)}[/]")
            return False

        console.print(f"\n[bold cyan]Installing required packages: {', '.join(packages)}...[/]")
        try:
            to_install = [f"{p}{known[p]}" for p in packages]
            # Run pip directly so its real-time download progress (in MB) is displayed
            subprocess.check_call([sys.executable, "-m", "pip", "install", *to_install])
            console.print("[bold green]✓ Packages installed successfully![/]")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]✗ Failed to install packages:[/] {e}")
            return False

    @staticmethod
    def install_gpu_support() -> bool:
        """Install NVIDIA CUDA runtime libraries via pip subprocess."""
        console.print("\n[bold cyan]Installing NVIDIA GPU support...[/]")
        console.print("[dim]Downloading ~1.2 GB of CUDA 12 runtimes. This only happens once.[/dim]\n")
        
        try:
            # Use pinned versions from REQUIRED_PACKAGES for reproducibility
            gpu_packages = REQUIRED_PACKAGES["GPU Acceleration (Optional)"]
            install_specs = [f"{pkg}{ver}" for pkg, ver in gpu_packages.items()
                            if pkg.startswith("nvidia")]
            # Run pip directly without -q or spinner so real-time download progress (in MB) is displayed
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                *install_specs
            ])
            console.print("[bold green]✓ GPU dependencies installed successfully![/]")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]✗ Failed to install GPU support:[/] {e}")
            return False

    @staticmethod
    def is_document_support_installed() -> bool:
        """Check if document extraction libraries are installed."""
        try:
            __import__("fitz")      # PyMuPDF
            __import__("docx")      # python-docx
            __import__("pptx")      # python-pptx
            __import__("ebooklib")  # EbookLib
            __import__("bs4")       # beautifulsoup4
            return True
        except ImportError:
            return False

    @staticmethod
    def is_ocr_installed() -> bool:
        """Check if EasyOCR is installed."""
        try:
            __import__("easyocr")
            return True
        except ImportError:
            return False

    @staticmethod
    def install_document_support() -> bool:
        """Install document extraction libraries (PyMuPDF, python-docx, etc.) via pip."""
        console.print("\n[bold cyan]Installing document extraction support...[/]")
        console.print("[dim]Downloading PDF, DOCX, PPTX, and EPUB libraries.[/dim]\n")

        try:
            doc_packages = REQUIRED_PACKAGES["Document Extraction (Auto-installed)"]
            install_specs = [f"{pkg}{ver}" for pkg, ver in doc_packages.items()]
            with console.status("[bold green]Pip is installing document libraries...[/]"):
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", "-q",
                    *install_specs
                ])
            console.print("[bold green]✓ Document extraction libraries installed![/]")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]✗ Failed to install document support:[/] {e}")
            return False

    @staticmethod
    def install_ocr_support() -> bool:
        """Install EasyOCR via pip. Downloads ~200 MB of OCR models on first use."""
        console.print("\n[bold cyan]Installing OCR engine (EasyOCR)...[/]")
        console.print("[dim]EasyOCR will download language models (~100-200 MB) on first OCR use.[/dim]\n")

        try:
            ocr_packages = REQUIRED_PACKAGES["OCR Engine (Auto-installed)"]
            install_specs = [f"{pkg}{ver}" for pkg, ver in ocr_packages.items()]
            with console.status("[bold green]Pip is installing EasyOCR...[/]"):
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", "-q",
                    *install_specs
                ])
            console.print("[bold green]✓ EasyOCR installed successfully![/]")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]✗ Failed to install EasyOCR:[/] {e}")
            return False

@contextlib.contextmanager
def silenced_output():
    """Redirects stdout and stderr to devnull, yielding a console that writes to the original stdout."""
    try:
        old_stdout_fd = sys.stdout.fileno()
        old_stderr_fd = sys.stderr.fileno()
    except (AttributeError, io.UnsupportedOperation):
        # Fallback if fileno() is not supported (e.g. some IDE consoles or testing environments)
        yield None
        return

    # Duplicate original file descriptors
    saved_stdout_fd = os.dup(old_stdout_fd)
    saved_stderr_fd = os.dup(old_stderr_fd)
    
    try:
        with open(os.devnull, "w") as fnull:
            null_fd = fnull.fileno()
            os.dup2(null_fd, old_stdout_fd)
            os.dup2(null_fd, old_stderr_fd)
            
            # Open the saved stdout fd for our private console output
            with os.fdopen(saved_stdout_fd, "w", encoding="utf-8", closefd=False) as private_out:
                yield Console(file=private_out)
    finally:
        # Restore original descriptors, ensuring cleanup even if one restore fails
        try:
            os.dup2(saved_stdout_fd, old_stdout_fd)
        finally:
            os.close(saved_stdout_fd)
        try:
            os.dup2(saved_stderr_fd, old_stderr_fd)
        finally:
            os.close(saved_stderr_fd)

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
    def get_repo_stats(repo_id: str) -> Tuple[int, int]:
        """Fetch total repository size and file count from Hugging Face API."""
        try:
            api = HfApi()
            info = api.model_info(repo_id, files_metadata=True)
            total_size = sum(s.size for s in info.siblings if s.size is not None)
            file_count = len(info.siblings)
            return total_size, file_count
        except Exception:
            logger.debug("Failed to fetch repo stats for %s", repo_id, exc_info=True)
            return 0, 0

    def download_model(self, variant: str) -> bool:
        """Download a model variant with a high-fidelity progress bar."""
        if not variant:
            raise ValueError("Model variant name is required.")
        variant = variant.upper()
        if variant not in MODEL_VARIANTS:
            raise ValueError(f"Unknown variant: {variant}")
            
        repo_id = MODEL_VARIANTS[variant]
        local_dir = get_model_path(variant)
        
        console.print(f"\n[bold]Model Download: {variant}[/]")
        console.print(f"[dim]Repository: {repo_id}[/dim]\n")
        
        total_size, file_count = self.get_repo_stats(repo_id)
        
        try:
            with silenced_output() as local_console:
                if local_console is None:
                    # Fallback for environments where fileno() isn't available
                    return self._download_fallback(variant, repo_id, local_dir)

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
            return True
        except Exception as e:
            logger.debug("Download error for %s", variant, exc_info=True)
            console.print(f"[bold red]✗ Download error:[/] {e}")
            return False

    def _download_fallback(self, variant, repo_id, local_dir) -> bool:
        """Simple download without redirection if OS-level hooks fail."""
        try:
            with Progress(
                SpinnerColumn(spinner_name="dots"),
                TextColumn(f"[bold cyan]Fetching {variant}…"),
                TimeElapsedColumn(),
                expand=False,
            ) as progress:
                progress.add_task("Downloading", total=None)
                disable_progress_bars()
                try:
                    snapshot_download(repo_id=repo_id, local_dir=local_dir)
                finally:
                    enable_progress_bars()
            return True
        except Exception as e:
            logger.debug("Fallback download error for %s", variant, exc_info=True)
            console.print(f"[bold red]✗ Fallback download error:[/] {e}")
            return False
