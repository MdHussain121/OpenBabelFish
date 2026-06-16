import os
import sys
import warnings
# Suppress UserWarning and DeprecationWarning to keep CLI/TUI outputs clean of library noise
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Reconfigure stdout/stderr to UTF-8 on Windows to prevent UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import argparse
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.padding import Padding
from rich.prompt import Confirm, Prompt
from rich import box
from rich.align import Align
from rich.live import Live
import shlex

from .config import load_config, save_config, get_model_path, BASE_DIR, CONFIG_FILE
from .engine import TranslationEngine
from .managers import DependencyManager, ModelManager, VARIANT_INFO

console = Console()

# ── LOGO ─────────────────────────────────────────────────────────────────────
LOGO = Text.assemble(
    ("  ██████╗ ██████╗ ███████╗███╗   ██╗ ██████╗  █████╗ ██████╗ ███████╗██╗     ███████╗██╗███████╗██╗  ██╗\n", "bold bright_cyan"),
    (" ██╔═══██╗██╔══██╗██╔════╝████╗  ██║ ██╔══██╗██╔══██╗██╔══██╗██╔════╝██║     ██╔════╝██║██╔════╝██║  ██║\n", "bold cyan"),
    (" ██║   ██║██████╔╝█████╗  ██╔██╗ ██║ ██████╔╝███████║██████╔╝█████╗  ██║     █████╗  ██║███████╗███████║\n", "bold cyan"),
    (" ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║ ██╔══██╗██╔══██║██╔══██╗██╔══╝  ██║     ██╔══╝  ██║╚════██║██╔══██║\n", "bold blue"),
    (" ╚██████╔╝██║     ███████╗██║ ╚████║ ██████╔╝██║  ██║██████╔╝███████╗███████╗██║     ██║███████║██║  ██║\n", "bold blue"),
    ("  ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝\n", "bold bright_blue"),
    ("  🐡  Offline Universal Translator  ·  Powered by Meta NLLB-200\n", "dim italic"),
)

def _print_logo():
    console.print()
    if console.width >= 105:
        console.print(Align.center(LOGO))
    else:
        compact_logo = Text.assemble(
            (" 🐡  ", ""),
            ("Open", "bold bright_cyan"),
            ("Babel", "bold cyan"),
            ("Fish", "bold blue"),
            ("  ·  Offline Universal Translator  ·  Powered by Meta NLLB-200", "dim italic")
        )
        console.print(Align.center(compact_logo))


def _print_divider(title: str = "", style: str = "bright_black"):
    if title:
        console.print(Rule(f" {title} ", style=style, characters="─"))
    else:
        console.print(Rule(style=style, characters="─"))


def double_space_text(text: Text, console: Console, panel_padding_width: int = 6) -> Text:
    """Wrap the text to the console width and insert empty lines between wrapped lines."""
    width = (console.width or 80) - panel_padding_width
    if width <= 0:
        width = 40
    lines = text.wrap(console, width)
    spaced_text = Text()
    for i, line in enumerate(lines):
        spaced_text.append(line)
        if i < len(lines) - 1:
            if len(line.plain.strip()) == 0 or len(lines[i+1].plain.strip()) == 0:
                spaced_text.append("\n")
            else:
                spaced_text.append("\n\n")
    return spaced_text


def make_progress_bar(label: str, percentage: int) -> Text:
    """Create a premium, quantized progress bar."""
    filled = percentage // 5
    bar = "█" * filled + "░" * (20 - filled)
    return Text.assemble(
        (f"  {label:<22} ", "bold cyan"),
        (f"[{bar}] ", "green"),
        (f"{percentage}%", "bold white")
    )


# ── HELP ──────────────────────────────────────────────────────────────────────
class SafeArgumentParser(argparse.ArgumentParser):
    """Custom parser for the REPL to prevent system exits and usage prints on errors."""
    def error(self, message):
        raise argparse.ArgumentError(None, message)

    def exit(self, status=0, message=None):
        if message:
            console.print(f"[bold red]Parser Exit:[/] {message}")

class OpenBabelFishHelpFormatter(argparse.HelpFormatter):
    """Suppress argparse's default output. Rich handles all rendering."""
    def format_help(self):
        _print_logo()
        _print_divider()

        # Usage
        usage_text = Text.assemble(
            ("Usage  ", "bold bright_cyan"), 
            ("openbabelfish ", "bold green"), 
            ("[OPTIONS]", "dim"),
            ("\n         (The 'openbabelfish' prefix is optional in shell mode)", "dim italic")
        )
        console.print(Align.center(usage_text))
        console.print()

        # Description box
        console.print(Align.center(Panel(
            "[dim]A high-performance, fully-offline translation appliance powered by Meta's NLLB-200.\n"
            "Handles model management and hardware acceleration automatically.[/dim]",
            border_style="bright_black",
            expand=False,
            padding=(1, 4),
        )))
        console.print()

        # Unified Table (Centered, Perfectly Symmetrical)
        options_table = Table(
            box=box.ROUNDED,
            border_style="bright_black",
            header_style="bold cyan",
            show_header=True,
            expand=False,
            padding=(0, 1),
        )
        options_table.add_column("Command / Option", style="bold cyan", width=26)
        options_table.add_column("Description", width=42)

        # Hardware Options
        options_table.add_row("[bold blue]🖥  Hardware Options[/bold blue]", "")
        options_table.add_row("--cpu, cpu", "Default. Runs on any machine. Reliable and portable.")
        options_table.add_row("--gpu, gpu, cuda", "CUDA acceleration. Requires NVIDIA GPU.\nDownloads ~1.2 GB of CUDA runtimes on first use.")
        options_table.add_section()

        # Model Management
        options_table.add_row("[bold cyan]📦  Model Management[/bold cyan]", "")
        options_table.add_row("-m, --model, m, model <name>", "Load a specific downloaded variant (e.g. 600M, 1.3B).")
        options_table.add_row("--add-model, add, download <name>", "Download a new variant from the Hugging Face registry.")
        options_table.add_row("--models, models, list", "Show all variants with download status and disk sizes.")
        options_table.add_row("--packages, packages, pkg, audit", "Audit and install Python dependencies (pip requirements).")
        options_table.add_section()

        # Translation Options
        options_table.add_row("[bold green]🌐  Translation Options[/bold green]", "")
        options_table.add_row("--to, to, target <lang>", "Target language (e.g. spanish, french, japanese).")
        options_table.add_row("--from, from, source <lang>", "Source language. Auto-detected if omitted.")
        options_table.add_row("-f, --file, f, file, read <path>", "Read input from a file. Supports: .txt .pdf .docx .pptx .epub")
        options_table.add_row("-o, --output, o, output, save <path>", "Write the translated text to a file.")
        options_table.add_row("--ocr, ocr", "Force OCR on PDF files (uses EasyOCR). Auto-detects by default.")
        options_table.add_row("--ocr-device, ocr-device, ocr_device <dev>", "Set device for OCR engine (cpu or gpu). Defaults to cpu.")

        console.print(Align.center(options_table))
        console.print()

        # Examples Panel (Centered, cleanly padded, box=None internally)
        eg_table = Table(box=None, show_header=False, padding=(0, 2))
        eg_table.add_column(style="dim")
        eg_table.add_row("[bold cyan]✦ Standard CLI Files[/bold cyan]")
        eg_table.add_row("[bold green]openbabelfish[/] -f [italic]path/to/file.txt[/italic] --to japanese")
        eg_table.add_row("[bold green]openbabelfish[/] -f [italic]document.pdf[/italic] --to spanish --from english")
        eg_table.add_row("[bold green]openbabelfish[/] -f [italic]scanned.pdf[/italic] --to french --ocr --ocr-device gpu")
        eg_table.add_row("")
        eg_table.add_row("[bold cyan]✦ Generalized Commands (REPL / CLI)[/bold cyan]")
        eg_table.add_row("file [italic]sample_document.docx[/italic] to spanish")
        eg_table.add_row("read [italic]scanned.pdf[/italic] target french ocr")
        eg_table.add_row("m 1.3B f [italic]book.epub[/italic] to arabic from english")
        eg_table.add_row("add 1.3B                               [dim]# Download new NLLB model[/dim]")
        eg_table.add_row("models                                 [dim]# Show model library[/dim]")
        eg_table.add_row("packages                               [dim]# Audit packages/dependencies[/dim]")
        eg_table.add_row("gpu                                    [dim]# Toggle CUDA acceleration[/dim]")
        eg_table.add_row("")
        eg_table.add_row("[bold cyan]✦ Quick Direct Translation (REPL)[/bold cyan]")
        eg_table.add_row("spanish: Hello, how are you today?")
        eg_table.add_row("hindi: OpenBabelFish is an offline translator.")
        
        console.print(Align.center(Panel(
            eg_table, 
            title="[bold bright_black]✦ Examples[/bold bright_black]", 
            border_style="bright_black", 
            expand=False, 
            padding=(1, 2)
        )))
        console.print()

        return ""


# ── SYSTEM SANITY & ONBOARDING ───────────────────────────────────────────────
def prompt_and_download_nllb(config, model_mgr):
    """Prompt the user to select and download an NLLB variant."""
    console.print()
    console.print(Align.center(Text("⚠  No translation model configured or model is missing/incomplete.", style="bold yellow")))
    variants = list(model_mgr.get_available_variants().keys())
    
    sel_table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, header_style="bold cyan", padding=(0, 2))
    sel_table.add_column("#", style="bold cyan", justify="center", width=3)
    sel_table.add_column("Variant", style="bold white")
    sel_table.add_column("Size & Description", style="dim")
    for i, v in enumerate(variants, 1):
        sel_table.add_row(str(i), v, VARIANT_INFO[v])
    console.print(Align.center(sel_table))

    idx = Prompt.ask("\n  [bold]Choose NLLB variant to download[/]", choices=[str(i) for i in range(1, len(variants)+1)], default="1")
    choice = variants[int(idx) - 1]
    console.print()
    console.print(Align.center(Text.assemble(
        ("✓  ", "bold green"),
        ("Selected: ", ""),
        (choice, "bold cyan")
    )))
    console.print()

    model_mgr.download_model(choice)

    config["model_variant"] = choice
    config["model_path"] = str(get_model_path(choice).absolute())
    if "quantization" not in config:
        config["quantization"] = "int8"
    if "device" not in config:
        is_gpu = False
        try:
            import torch
            is_gpu = torch.cuda.is_available()
        except Exception:
            pass
        config["device"] = "cuda" if is_gpu else "cpu"
    save_config(config)

def ensure_system_sanity(config, model_mgr, dep_mgr):
    """
    Ensures all dependencies, OCR models, and at least one translation model are present.
    If anything is missing, downloads it.
    """
    # Check if this is the first start (config file doesn't exist yet)
    if not CONFIG_FILE.exists():
        console.clear()
        _print_logo()
        console.print(Align.center(Panel(
            f"[bold bright_cyan]Welcome to OpenBabelFish![/]\n"
            f"[dim]Storage Location: [cyan]{BASE_DIR}[/][/dim]",
            box=box.DOUBLE_EDGE,
            border_style="cyan",
            expand=False,
            padding=(1, 4),
        )))
        console.print()
        
        # GPU Detection and prompt
        is_gpu = False
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                console.print(Align.center(Panel(
                    f"[bold green]✓  NVIDIA GPU Detected[/]\n"
                    f"[dim]Device: [cyan]{gpu_name}[/cyan][/dim]",
                    border_style="green",
                    expand=False,
                    padding=(1, 4),
                )))
                if Confirm.ask("\n  Enable GPU acceleration? [dim](Downloads ~1.2 GB once)[/dim]", default=True):
                    if dep_mgr.install_gpu_support():
                        is_gpu = True
                        console.print(Align.center(Panel("[bold green]✓  GPU Acceleration Ready[/]", border_style="green", expand=False, padding=(0, 2))))
        except Exception:
            console.print(Align.center(Text("No NVIDIA GPU detected — using CPU mode.", style="dim")))
        
        config["device"] = "cuda" if is_gpu else "cpu"
        save_config(config)
        console.print()

    # 1. Audit packages and download missing ones automatically
    results = dep_mgr.check_dependencies()
    missing_packages = []
    for r in results:
        # Check Core, Document, and OCR categories. Optional is fine.
        if r["status"] != "installed" and "Optional" not in r["group"] and "Utility" not in r["group"]:
            missing_packages.append(r["package"])
            
    if missing_packages:
        console.print(f"\n[bold yellow]⚠  Missing required packages detected: {', '.join(missing_packages)}[/bold yellow]")
        console.print("[dim]Installing missing dependencies...[/dim]")
        dep_mgr.install_missing(missing_packages)

    # 2. Check OCR models if easyocr is installed
    if dep_mgr.is_ocr_installed():
        ocr_model_dir = Path(os.path.expanduser('~')) / '.EasyOCR' / 'model'
        detector_file = ocr_model_dir / 'craft_mlt_25k.pth'
        recognition_file = ocr_model_dir / 'english_g2.pth'
        
        if not detector_file.exists() or not recognition_file.exists():
            # Clean up corrupted partial downloads to avoid zlib decompression errors
            if ocr_model_dir.exists():
                for zip_file in ocr_model_dir.glob("*.zip"):
                    try:
                        zip_file.unlink()
                    except Exception:
                        pass
                for pth_file in [detector_file, recognition_file]:
                    if not pth_file.exists():
                        try:
                            pth_file.unlink(missing_ok=True)
                        except Exception:
                            pass

            console.print("\n[bold cyan]📥  Pre-downloading OCR models (~100-200 MB)... This only happens once.[/bold cyan]")
            try:
                import subprocess
                cmd = [
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.reconfigure(encoding='utf-8') if sys.platform=='win32' else None; import easyocr; easyocr.Reader(['en'], gpu=False)"
                ]
                subprocess.check_call(cmd)
                console.print("[bold green]✓  OCR models downloaded successfully![/bold green]\n")
            except Exception as e:
                console.print(f"[bold red]✗  Failed to pre-download OCR models:[/] {e}")

    # 3. Check NLLB model
    active_model = config.get("model_variant")
    if not active_model or model_mgr.get_model_status(active_model) != "DOWNLOADED":
        prompt_and_download_nllb(config, model_mgr)


def _build_parser(safe=False) -> argparse.ArgumentParser:
    """Centralized argument parser definition used by both CLI and REPL modes."""
    cls = SafeArgumentParser if safe else argparse.ArgumentParser
    p = cls(formatter_class=OpenBabelFishHelpFormatter, add_help=False, allow_abbrev=False)
    p.add_argument("--to", dest="target_lang")
    p.add_argument("--from", dest="source_lang")
    p.add_argument("--file", "-f")
    p.add_argument("--output", "-o")
    p.add_argument("--model", "-m", "-model")
    p.add_argument("--add-model", dest="add_model")
    p.add_argument("--models", action="store_true")
    p.add_argument("--packages", action="store_true")
    p.add_argument("--gpu", action="store_true")
    p.add_argument("--cpu", action="store_true")
    p.add_argument("--ocr", action="store_true", help="Force OCR on PDF files")
    p.add_argument("--ocr-device", choices=["cpu", "gpu"], help="Set device for OCR (default: cpu)")
    p.add_argument("--translate", "-t", action="store_true", help="Start interactive translation mode")
    p.add_argument("--help", "-h", action="help" if not safe else "store_true")
    p.add_argument("text", nargs="*", help="Direct text to translate")
    return p


def _run_translation(args, config, model_mgr, dep_mgr):
    """Core translation logic extracted for reuse in CLI and REPL."""
    ensure_system_sanity(config, model_mgr, dep_mgr)
    config = load_config()

    if getattr(args, 'ocr_device', None):
        config["ocr_device"] = args.ocr_device
        save_config(config)

    # Hardware switching (updates both local state and session config)
    current_device = config.get("device", "cpu")
    
    if args.gpu:
        if not dep_mgr.is_gpu_installed():
            console.print(Align.center(Panel(
                "[bold yellow]CUDA libraries not found.[/]\n"
                "[dim]OpenBabelFish needs to download ~1.2 GB of NVIDIA runtimes.[/dim]",
                border_style="yellow", expand=False, padding=(1, 2)
            )))
            if Confirm.ask("  Download GPU libraries now?"):
                if dep_mgr.install_gpu_support():
                    current_device = "cuda"
                    config["device"] = "cuda"
                    save_config(config)
        else:
            current_device = "cuda"
            config["device"] = "cuda"
            save_config(config)
    elif args.cpu:
        current_device = "cpu"
        config["device"] = "cpu"
        save_config(config)

    # Model selection (updates both local state and session config)
    requested_model = args.model or config.get("model_variant", "600M")
    model_variant = model_mgr.resolve_variant(requested_model)

    if args.model:
        config["model_variant"] = model_variant
        save_config(config)
        
    model_path = get_model_path(model_variant)
    if model_path:
        config["model_path"] = str(model_path.absolute())

    model_status = model_mgr.get_model_status(model_variant)
    if model_status != "DOWNLOADED":
        status_label = "incomplete" if model_status == "INCOMPLETE" else "not downloaded"
        console.print(Align.center(Panel(
            f"[bold yellow]Model '{model_variant}' is {status_label}.[/]",
            border_style="yellow", expand=False, padding=(1, 2)
        )))
        if Confirm.ask(f"  {'Fix' if model_status == 'INCOMPLETE' else 'Download'} {model_variant} now?"):
            model_mgr.download_model(model_variant)
        else:
            return

    # Input handling (File vs stdin vs arguments)
    text = ""
    ocr_was_run = False
    is_tty = sys.stdout.isatty()
    is_repl = hasattr(sys, '_openbabelfish_repl') and sys._openbabelfish_repl

    if args.file:
        file_path = args.file.strip('"\'')
        try:
            from .extractors import FileExtractor, SUPPORTED_EXTENSIONS, ExtractionError
            ext = Path(file_path).suffix.lower()
            if ext in SUPPORTED_EXTENSIONS:
                extractor = FileExtractor(dep_mgr)
                force_ocr = getattr(args, 'ocr', False)
                
                progress_callback = None
                if is_tty and not is_repl:
                    live_ocr = Live(Text(""), console=console, refresh_per_second=10)
                    live_ocr.start()
                    
                    def ocr_progress_callback(page_num, total_pages):
                        nonlocal ocr_was_run
                        ocr_was_run = True
                        pct = int((page_num / total_pages) * 100)
                        display_pct = (pct // 10) * 10
                        ocr_bar = make_progress_bar("OCR Progress", display_pct)
                        live_ocr.update(Panel(
                            ocr_bar,
                            title="[bold cyan]Document Extraction (OCR)[/bold cyan]",
                            border_style="cyan",
                            padding=(1, 2)
                        ))
                    
                    progress_callback = ocr_progress_callback
                
                try:
                    text = extractor.extract(file_path, force_ocr=force_ocr, progress_callback=progress_callback)
                finally:
                    if is_tty and not is_repl and progress_callback is not None:
                        live_ocr.stop()
            else:
                # Fallback: try reading as plain text for unknown extensions
                text = Path(file_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            console.print(Align.center(Panel(f"[bold red]File not found:[/] {file_path}", border_style="red", expand=False, padding=(1, 2))))
            return
        except ExtractionError as e:
            console.print(Align.center(Panel(f"[bold red]Extraction Error:[/] {e}", border_style="red", expand=False, padding=(1, 2))))
            return
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    elif hasattr(args, 'text') and args.text:
        text = " ".join(args.text)
    
    if not text.strip():
        # Check if we just did a hardware switch or model switch without text
        if args.gpu or args.cpu or args.model or args.add_model or getattr(args, 'ocr_device', None):
            hw_name = "⚡ CUDA (GPU)" if current_device == "cuda" else "⚙  CPU"
            console.print()
            console.print(Align.center(Text.assemble(
                ("✓  ", "bold green"),
                ("Mode set to ", ""),
                (hw_name, "bold cyan"),
                (" (Model: ", ""),
                (model_variant, "bold magenta"),
                (")", "")
            )))
            if getattr(args, 'ocr_device', None):
                console.print(Align.center(Text.assemble(
                    ("✓  ", "bold green"),
                    ("OCR device set to ", ""),
                    (args.ocr_device.upper(), "bold cyan")
                )))
            console.print()
            return

        # Otherwise show standard help/logo (but skip logo if in REPL session)
        is_repl = hasattr(sys, '_openbabelfish_repl') and sys._openbabelfish_repl
        if not is_repl:
            _print_logo()
        
        console.print(Align.center(Panel(
            "[bold yellow]⚠  No input text detected.[/] \n\n"
            "[dim]Please use [cyan]--file path/to/file[/cyan] to translate a file,\n"
            "or type [cyan]--help[/cyan] to see available flags.\n\n"
            "[italic]Note: [cyan]--from[/cyan] is for the source language name (e.g. 'spanish'), not file paths.[/italic][/dim]",
            border_style="bright_black",
            expand=False,
            padding=(1, 4),
        )))
        return

    if not args.target_lang:
        console.print(Align.center(Panel("[bold red]✗  Please specify a target language with [cyan]--to[/cyan][/bold red]", border_style="red", expand=False, padding=(1, 2))))
        return

    # Check if stdout is a TTY to select interface style
    is_tty = sys.stdout.isatty()

    if is_tty:
        try:
            # Check for cached engine in REPL mode
            engine = None
            is_repl = hasattr(sys, '_openbabelfish_repl') and sys._openbabelfish_repl
            if is_repl and hasattr(sys, '_openbabelfish_engine') and sys._openbabelfish_engine:
                cached = sys._openbabelfish_engine
                if cached.device == current_device and cached.model_path == str(model_path.absolute()):
                    engine = cached
                    
            if engine is None:
                with console.status("[bold cyan]Initializing Engine...[/]", spinner="arc"):
                    engine = TranslationEngine(model_path=str(model_path.absolute()), device=current_device)
                if is_repl:
                    sys._openbabelfish_engine = engine

            result_chunks = []
            translated_text = ""

            if is_repl:
                console.print()
                console.print("[bold magenta]🐡 OpenBabelFish ❯[/]")
                
                first = True
                for chunk in engine.translate(text, args.target_lang, args.source_lang, stream=True):
                    result_chunks.append(chunk)
                    translated_text += chunk
                    
                    formatted_chunk = chunk.replace("\n", "\n  ")
                    if first:
                        console.print("  " + formatted_chunk, end="", highlight=False)
                        first = False
                    else:
                        console.print(formatted_chunk, end="", highlight=False)
                console.print()
                console.print()
            else:
                if args.file:
                    total_paragraphs = len([p for p in text.split("\n\n") if p.strip()])
                    translated_paragraphs = []
                    
                    if total_paragraphs > 0:
                        with Live(Text(""), console=console, refresh_per_second=10) as live:
                            def update_display(pct_completed: int):
                                layout = Table.grid(padding=(1, 0))
                                layout.add_column()
                                
                                if ocr_was_run:
                                    ocr_bar = make_progress_bar("OCR Progress", 100)
                                    layout.add_row(ocr_bar)
                                    
                                trans_bar = make_progress_bar("Translation Progress", pct_completed)
                                layout.add_row(trans_bar)
                                layout.add_row(Rule(style="dim"))
                                
                                translated_text_so_far = "\n\n".join(translated_paragraphs)
                                layout.add_row(Panel(
                                    Text(translated_text_so_far, style="bright_green"),
                                    title="[bold green]✦ TRANSLATION OUTPUT ✦[/bold green]",
                                    title_align="center",
                                    border_style="green",
                                    box=box.ROUNDED,
                                    expand=True,
                                    padding=(1, 2)
                                ))
                                live.update(layout)

                            update_display(0)

                            current_count = 0
                            for chunk in engine.translate(text, args.target_lang, args.source_lang, stream=False):
                                if chunk != "\n\n":
                                    translated_paragraphs.append(chunk)
                                    current_count += 1
                                    pct = int((current_count / total_paragraphs) * 100)
                                    display_pct = (pct // 10) * 10
                                    update_display(display_pct)
                            
                            update_display(100)
                            translated_text = "\n\n".join(translated_paragraphs)
                    else:
                        translated_text = ""
                else:
                    src_label = args.source_lang or "auto"
                    hw_color  = "bright_green" if current_device == "cuda" else "bright_yellow"

                    meta_table = Table.grid(padding=(0, 3))
                    meta_table.add_column(style="dim")
                    meta_table.add_column()
                    meta_table.add_row("Engine",    "[green]NLLB-200 / CTranslate2[/]")
                    meta_table.add_row("Hardware",  f"[{hw_color}]{'⚡ CUDA (GPU)' if current_device == 'cuda' else '⚙  CPU'}[/]")
                    meta_table.add_row("Model",     f"[cyan]{model_variant}[/]")
                    meta_table.add_row("Direction", f"[dim]{src_label}[/dim]  [bold bright_white]→[/]  [bold magenta]{args.target_lang}[/]")

                    console.print()
                    console.print(Align.center(Panel(
                        meta_table,
                        title="[bold]🐡  OpenBabelFish[/bold]",
                        subtitle="[dim]translation in progress…[/dim]",
                        border_style="cyan",
                        expand=False,
                        padding=(0, 2),
                    )))
                    console.print()

                    with Live(Text(""), console=console, refresh_per_second=10) as live:
                        for chunk in engine.translate(text, args.target_lang, args.source_lang, stream=True):
                            result_chunks.append(chunk)
                            translated_text += chunk
                            live.update(Panel(
                                Text(translated_text, style="bright_green"),
                                title="[bold green]✦ TRANSLATION OUTPUT ✦[/bold green]",
                                title_align="center",
                                border_style="green",
                                box=box.ROUNDED,
                                expand=True,
                                padding=(1, 2)
                            ))
                console.print()

            if args.output:
                out_path = args.output.strip('"\'')
                p = Path(out_path)
                if p.is_dir():
                    if args.file:
                        input_name = Path(args.file.strip('"\'')).stem
                        out_path = str(p / f"{input_name}_translated.txt")
                    else:
                        out_path = str(p / "translation.txt")
                Path(out_path).write_text(translated_text, encoding="utf-8")
                console.print(Align.center(Panel(
                    f"[green]✓  Saved to:[/] [cyan]{out_path}[/]",
                    border_style="green",
                    expand=False,
                    padding=(0, 2)
                )))
                console.print()

        except Exception as e:
            err_msg = str(e)
            if sys.platform == "win32" and "cublas" in err_msg:
                err_msg += "\n\n[yellow]Hint: On Windows, GPU acceleration requires CUDA runtime DLLs. " \
                           "Please run [bold cyan]openbabelfish --packages[/bold cyan] and choose to install/repair " \
                           "GPU dependencies to solve this issue.[/yellow]"
            console.print(Align.center(Panel(
                f"[bold red]✗  Translation Error[/]\n[dim]{err_msg}[/dim]",
                border_style="red",
                expand=False,
                padding=(1, 2),
            )))
    else:
        # Non-interactive CLI mode (pipes / redirects)
        try:
            engine = TranslationEngine(model_path=str(model_path.absolute()), device=current_device)
            result_chunks = []
            for chunk in engine.translate(text, args.target_lang, args.source_lang, stream=False):
                result_chunks.append(chunk)
                sys.stdout.write(chunk)
                sys.stdout.flush()
            
            if args.output:
                out_path = args.output.strip('"\'')
                p = Path(out_path)
                if p.is_dir():
                    if args.file:
                        input_name = Path(args.file.strip('"\'')).stem
                        out_path = str(p / f"{input_name}_translated.txt")
                    else:
                        out_path = str(p / "translation.txt")
                Path(out_path).write_text("".join(result_chunks), encoding="utf-8")
        except Exception as e:
            err_msg = str(e)
            if sys.platform == "win32" and "cublas" in err_msg:
                err_msg += "\nHint: On Windows, GPU acceleration requires CUDA runtime DLLs. Run 'openbabelfish --packages' to install them."
            sys.stderr.write(f"Translation Error: {err_msg}\n")
            sys.exit(1)




def interactive_shell(start_translate=False, target_lang=None, source_lang=None):
    """High-fidelity interactive REPL using Rich."""
    # Mark the session so _run_translation knows we are in a REPL
    sys._openbabelfish_repl = True
    
    config = load_config()
    model_mgr = ModelManager()
    dep_mgr = DependencyManager()

    ensure_system_sanity(config, model_mgr, dep_mgr)
    config = load_config()

    console.clear()
    _print_logo()
    
    # Session info (Centered)
    active_model = config.get("model_variant", "None")
    active_device = config.get("device", "cpu").upper()
    
    session_info = Text.assemble(
        ("Session Active ", "bold bright_black"),
        (f"[{active_model}] ", "bold cyan"),
        (f"[{active_device}] ", "bold green"),
        (f"({BASE_DIR})", "dim italic")
    )
    console.print(Align.center(session_info))
    console.print(Align.center(Text("Type exit to quit. Use --help for options.", style="dim")))
    console.print()

    # Pre-configure parser for the REPL
    shell_parser = _build_parser(safe=True)

    # Autocomplete mappings and setup
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
        'model': '--model', 'm': '--model',
        'translate': '--translate', 't': '--translate'
    }

    try:
        import readline
        completion_words = sorted(list(cmd_mappings.keys()) + [
            'exit', 'quit', '--to', '--from', '--file', '--output', '--model', 
            '--add-model', '--models', '--packages', '--gpu', '--cpu', '--ocr', '--ocr-device', '--help', '--translate'
        ])
        
        def completer(text, state):
            options = [w for w in completion_words if w.startswith(text)]
            if state < len(options):
                return options[state]
            return None
            
        readline.set_completer(completer)
        if 'libedit' in readline.__doc__:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
        readline.set_completer_delims(' \t\n;')
    except Exception:
        pass

    # Translation mode states
    in_translation_mode = start_translate
    mode_from_lang = source_lang
    mode_to_lang = target_lang

    if in_translation_mode:
        if not mode_from_lang:
            mode_from_lang = Prompt.ask("\n  [bold cyan]Enter input (source) language[/] [dim](press Enter for auto-detect)[/]").strip()
            if not mode_from_lang:
                mode_from_lang = "auto"
        if not mode_to_lang:
            mode_to_lang = Prompt.ask("  [bold cyan]Enter output (target) language[/] (e.g. spanish, french, hindi)").strip()
        if not mode_to_lang:
            in_translation_mode = False
            console.print("[yellow]⚠  Output (target) language required to enter translation mode.[/yellow]\n")
        else:
            console.print()
            console.print(Align.center(Panel(
                Text.assemble(
                    ("Interactive Translation Mode Active!\n", "bold green"),
                    (f"Direction: {mode_from_lang} ❯ {mode_to_lang}\n", "cyan"),
                    ("Type any sentence to translate. Type '--exit' to exit this mode.", "dim")
                ),
                border_style="green",
                expand=False,
                padding=(1, 2)
            )))
            console.print()

    while True:
        try:
            if in_translation_mode:
                prompt_text = Text.assemble(
                    ("openbabelfish [", "bold cyan"),
                    (f"{mode_from_lang} ❯ {mode_to_lang}", "bold magenta"),
                    ("] ❯ ", "bold bright_black")
                )
            else:
                prompt_text = Text.assemble(
                    ("openbabelfish", "bold cyan"),
                    (" ❯ ", "bold bright_black")
                )

            user_input = console.input(prompt_text).strip()
            
            if not user_input:
                continue
                
            if in_translation_mode:
                if user_input.lower() == "--exit":
                    in_translation_mode = False
                    console.print("[yellow]✓ Exited interactive translation mode.[/yellow]\n")
                    continue
                
                # Treat everything in translation mode as direct text to translate
                class DummyArgs:
                    pass
                args = DummyArgs()
                args.target_lang = mode_to_lang
                args.source_lang = None if mode_from_lang == "auto" else mode_from_lang
                args.file = None
                args.output = None
                args.model = None
                args.add_model = None
                args.models = False
                args.packages = False
                args.gpu = False
                args.cpu = False
                args.ocr = False
                args.ocr_device = None
                args.text = [user_input]
                _run_translation(args, config, model_mgr, dep_mgr)
                continue

            if user_input.lower() in ["exit", "quit"]:
                console.print("[dim]Goodbye![/]")
                break

            # Parse user input into tokens
            try:
                tokens = shlex.split(user_input)
            except ValueError as e:
                console.print(Align.center(Text(f"Command Error: {e}", style="bold red")))
                continue

            if not tokens:
                continue

            first_token_lower = tokens[0].lower()
            
            # Check if this is a direct translation prompt (e.g. "spanish: hello")
            is_direct_translation = ":" in user_input and not user_input.startswith("-") and first_token_lower.split(":")[0] not in cmd_mappings

            if not is_direct_translation:
                # Perform generalization of tokens
                generalized_tokens = []
                for token in tokens:
                    lower_token = token.lower()
                    if lower_token in cmd_mappings:
                        generalized_tokens.append(cmd_mappings[lower_token])
                    else:
                        generalized_tokens.append(token)

                # If first token doesn't start with dash (not mapped and not a standard option)
                if generalized_tokens and not generalized_tokens[0].startswith("-"):
                    first_word_clean = tokens[0].lower().lstrip('-')
                    all_possible_inputs = sorted(list(cmd_mappings.keys()) + [
                        'exit', 'quit', '--to', '--from', '--file', '--output', '--model', 
                        '--add-model', '--models', '--packages', '--gpu', '--cpu', '--ocr', '--ocr-device', '--help', '--translate'
                    ])
                    import difflib
                    close_matches = difflib.get_close_matches(first_word_clean, all_possible_inputs, n=3, cutoff=0.5)
                    prefix_matches = [w for w in all_possible_inputs if w.startswith(first_word_clean)]
                    suggestions = sorted(list(set(close_matches + prefix_matches)))
                    if suggestions:
                        console.print(Align.center(Text(f"Did you mean: {', '.join(suggestions)}?", style="bold yellow")))
                    else:
                        console.print(Align.center(Text(f"Unrecognized command: '{tokens[0]}'. Type 'help' for options.", style="bold red")))
                    continue

                # Parse as arguments
                try:
                    args = shell_parser.parse_args(generalized_tokens)
                    
                    if args.help:
                        shell_parser.print_help()
                        continue
                        
                    if args.models:
                        _handle_models_command(model_mgr, config)
                        continue

                    if args.packages:
                        _handle_packages_command(dep_mgr)
                        continue

                    if args.add_model:
                        _print_divider(f"Downloading {args.add_model}")
                        model_mgr.download_model(args.add_model)
                        continue

                    if getattr(args, 'translate', False):
                        in_translation_mode = True
                        mode_from_lang = args.source_lang
                        mode_to_lang = args.target_lang
                        
                        # Prompt input (source) lang if not specified
                        if not mode_from_lang:
                            mode_from_lang = Prompt.ask("\n  [bold cyan]Enter input (source) language[/] [dim](press Enter for auto-detect)[/]").strip()
                            if not mode_from_lang:
                                mode_from_lang = "auto"
                        
                        # Prompt output (target) lang if not specified
                        if not mode_to_lang:
                            mode_to_lang = Prompt.ask("  [bold cyan]Enter output (target) language[/] (e.g. spanish, french, hindi)").strip()
                        if not mode_to_lang:
                            in_translation_mode = False
                            console.print("[yellow]⚠  Output (target) language required to enter translation mode.[/yellow]\n")
                            continue
                                
                        if in_translation_mode:
                            console.print()
                            console.print(Align.center(Panel(
                                Text.assemble(
                                    ("Interactive Translation Mode Active!\n", "bold green"),
                                    (f"Direction: {mode_from_lang} ❯ {mode_to_lang}\n", "cyan"),
                                    ("Type any sentence to translate. Type '--exit' to exit this mode.", "dim")
                                ),
                                border_style="green",
                                expand=False,
                                padding=(1, 2)
                            )))
                            console.print()
                        continue

                    _run_translation(args, config, model_mgr, dep_mgr)
                except argparse.ArgumentError as e:
                    console.print(Align.center(Text(f"Usage Error: {e}", style="bold red")))
                except Exception as e:
                    console.print(Align.center(Text(f"Command Error: {e}", style="bold red")))
            else:
                # Direct text translation (Quick mode)
                if ":" in user_input:
                    lang, text = user_input.split(":", 1)
                    args = shell_parser.parse_args(["--to", lang.strip()])
                    args.text = [text.strip()]
                    _run_translation(args, config, model_mgr, dep_mgr)
                else:
                    console.print(Align.center(Text("⚠  Quick prompt requires a language. Try: 'spanish: Hello'", style="bold yellow")))

        except KeyboardInterrupt:
            console.print("\n[dim]Stopping session...[/]")
            break
        except Exception as e:
            console.print(Align.center(Text(f"Shell Error: {e}", style="bold red")))


def _handle_models_command(model_mgr, config):
    """Helper to display models table."""
    is_repl = hasattr(sys, '_openbabelfish_repl') and sys._openbabelfish_repl
    if not is_repl:
        _print_logo()
    _print_divider("Model Library")
    installed = model_mgr.get_installed_models()
    active = config.get("model_variant")

    t = Table(box=box.ROUNDED, border_style="cyan", header_style="bold cyan", show_header=True, padding=(0, 2))
    t.add_column("Variant", style="bold white")
    t.add_column("Status", justify="center")
    t.add_column("Info", style="dim")
    t.add_column("Active", justify="center")

    for v, info in VARIANT_INFO.items():
        status_code = model_mgr.get_model_status(v)
        if status_code == "DOWNLOADED":
            status = "[bold green]● Downloaded[/]"
        elif status_code == "INCOMPLETE":
            status = "[bold yellow]◑ Incomplete[/]"
        else:
            status = "[dim]○ Available[/]"
            
        active_mark = "[bold cyan]★ Yes[/]" if v == active else ""
        t.add_row(v, status, info, active_mark)

    console.print()
    console.print(Align.center(t))
    console.print()
    console.print(Align.center(Text.assemble(
        ("Library Path: ", "dim"),
        (f"{BASE_DIR}", "cyan"),
    )))
    console.print(Align.center(Text("Use --add-model to download more. Use --model to switch.", style="dim")))
    console.print()


def _handle_packages_command(dep_mgr):
    """Helper to audit and install dependencies with categorization."""
    _print_divider("Comprehensive Package Audit")
    results = dep_mgr.check_dependencies()
    
    t = Table(box=box.MINIMAL_DOUBLE_HEAD, border_style="cyan", header_style="bold cyan")
    t.add_column("Category", style="dim")
    t.add_column("Package", style="bold")
    t.add_column("Required")
    t.add_column("Installed")
    t.add_column("Status", justify="center")

    missing_core = []
    missing_gpu = []
    
    last_group = None
    for r in results:
        # Visual grouping
        display_group = r["group"] if r["group"] != last_group else ""
        last_group = r["group"]
        
        status_icon = "[bold green]✓[/]" if r["status"] == "installed" else "[bold red]✗[/]"
        
        # Track missing by category for smart prompts
        if r["status"] != "installed":
            if "Core" in r["group"]:
                missing_core.append(r["package"])
            elif "GPU" in r["group"]:
                missing_gpu.append(r["package"])
        
        t.add_row(display_group, r["package"], r["required"], r["installed"], status_icon)

    console.print()
    console.print(Align.center(t))
    console.print()
    
    # Smart prompts based on what's missing
    if missing_core:
         console.print(Align.center(Text(f"⚠ Critical Core packages are missing: {', '.join(missing_core)}", style="bold red")))
         if Confirm.ask("  Install core requirements now?"):
             dep_mgr.install_missing(missing_core)
    
    if missing_gpu:
         console.print(Align.center(Text(f"⚠ GPU Acceleration runtimes are missing: {', '.join(missing_gpu)}", style="bold yellow")))
         if Confirm.ask("  Install NVIDIA GPU runtimes?"):
             dep_mgr.install_missing(missing_gpu)

    if not missing_core and not missing_gpu:
        console.print(Align.center(Text("✓ Complete system audit passed. All modules synchronized.", style="bold green")))
    console.print()


def main():
    # Map of generalized commands
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
        'model': '--model', 'm': '--model',
        'translate': '--translate', 't': '--translate'
    }

    # Standard CLI Mode
    parser = _build_parser(safe=False)
    # If no arguments are passed, enter interactive mode
    if len(sys.argv) == 1:
        interactive_shell()
        return

    # Perform generalization of CLI arguments
    cli_args = []
    for arg in sys.argv[1:]:
        lower_arg = arg.lower()
        if lower_arg in cmd_mappings:
            cli_args.append(cmd_mappings[lower_arg])
        else:
            cli_args.append(arg)

    args = parser.parse_args(cli_args)
    
    config = load_config()
    model_mgr = ModelManager()
    dep_mgr = DependencyManager()

    # Priority 1: Configuration Changes (-m, --gpu, --cpu)
    # These update the config object for subsequent actions
    if args.model:
        model_variant = model_mgr.resolve_variant(args.model)
        config["model_variant"] = model_variant
        save_config(config)

    # Priority 2: Information Actions (--models, --packages)
    if args.models:
        _handle_models_command(model_mgr, config)
        return

    if args.packages:
        _handle_packages_command(dep_mgr)
        return

    # Setup is handled dynamically on execution or REPL start.

    if args.add_model:
        _print_divider(f"Downloading {args.add_model}")
        model_mgr.download_model(args.add_model)
        return

    if getattr(args, 'translate', False):
        if args.gpu:
            if dep_mgr.is_gpu_installed():
                config["device"] = "cuda"
                save_config(config)
        elif args.cpu:
            config["device"] = "cpu"
            save_config(config)
        interactive_shell(start_translate=True, target_lang=args.target_lang, source_lang=args.source_lang)
        return

    # Standard translation workflow
    _run_translation(args, config, model_mgr, dep_mgr)



if __name__ == "__main__":
    main()
