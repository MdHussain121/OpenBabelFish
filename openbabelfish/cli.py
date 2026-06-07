import sys
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
import shlex

from .config import is_setup_complete, load_config, save_config, get_model_path, BASE_DIR
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
    console.print(Align(LOGO, align="left"))


def _print_divider(title: str = "", style: str = "bright_black"):
    if title:
        console.print(Rule(f" {title} ", style=style, characters="─"))
    else:
        console.print(Rule(style=style, characters="─"))


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
        console.print(Padding(
            Text.assemble(
                ("Usage  ", "bold bright_cyan"), 
                ("openbabelfish ", "bold green"), 
                ("[OPTIONS]", "dim"),
                ("\n[italic dim]         (The 'openbabelfish' prefix is optional in shell mode)[/]", "")
            ),
            (1, 2)
        ))

        # Description box
        console.print(Panel(
            "[dim]A high-performance, fully-offline translation appliance powered by Meta's NLLB-200.\n"
            "Handles model management and hardware acceleration automatically.[/dim]",
            border_style="bright_black",
            expand=False,
            padding=(0, 2),
        ))
        console.print()

        # ── Hardware Modes ────────────────────────────────────────────────────
        hw_table = Table(
            box=box.ROUNDED,
            border_style="blue",
            header_style="bold blue",
            show_header=True,
            padding=(0, 2),
            expand=False,
        )
        hw_table.add_column("🖥  Hardware Flag", style="bold cyan", min_width=16)
        hw_table.add_column("Behaviour", style="", min_width=50)
        hw_table.add_row("--cpu", "[dim]Default. Runs on any machine. Reliable and portable.[/dim]")
        hw_table.add_row("--gpu", "[dim]CUDA acceleration. Requires NVIDIA GPU.\n[yellow]Downloads ~1.2 GB of CUDA runtimes on first use.[/yellow][/dim]")
        console.print(Padding(hw_table, (0, 2)))
        console.print()

        # ── Model Management ──────────────────────────────────────────────────
        mod_table = Table(
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
            show_header=True,
            padding=(0, 2),
            expand=False,
        )
        mod_table.add_column("📦  Model Flag", style="bold cyan", min_width=22)
        mod_table.add_column("Behaviour", min_width=50)
        mod_table.add_row("-m, --model, -model [italic]name[/italic]", "[dim]Load a specific downloaded variant (e.g. [cyan]600M[/cyan], [cyan]1.3B[/cyan]).[/dim]")
        mod_table.add_row("--add-model [italic]name[/italic]", "[dim]Download a new variant from the Hugging Face registry.[/dim]")
        mod_table.add_row("--models", "[dim]Show all variants with download status and disk sizes.[/dim]")
        mod_table.add_row("--packages", "[dim]Audit and install Python dependencies (pip requirements).[/dim]")
        console.print(Padding(mod_table, (0, 2)))
        console.print()

        # ── Translation Options ───────────────────────────────────────────────
        io_table = Table(
            box=box.ROUNDED,
            border_style="green",
            header_style="bold green",
            show_header=True,
            padding=(0, 2),
            expand=False,
        )
        io_table.add_column("🌐  Translation Flag", style="bold cyan", min_width=22)
        io_table.add_column("Behaviour", min_width=50)
        io_table.add_row("--to [italic]lang[/italic]", "[dim]Target language (e.g. [cyan]spanish[/cyan], [cyan]french[/cyan], [cyan]japanese[/cyan]).[/dim]")
        io_table.add_row("--from [italic]lang[/italic]", "[dim]Source language. Auto-detected if omitted.[/dim]")
        io_table.add_row("-f, --file [italic]path[/italic]", "[dim]Read input text from a local file.[/dim]")
        io_table.add_row("-o, --output [italic]path[/italic]", "[dim]Write the translated text to a file.[/dim]")
        console.print(Padding(io_table, (0, 2)))
        console.print()

        # ── Examples ──────────────────────────────────────────────────────────
        eg_table = Table(box=box.ROUNDED, border_style="bright_black", show_header=False, padding=(0, 2))
        eg_table.add_column(style="dim")
        eg_table.add_row("[bold green]openbabelfish[/] -f [italic]path/to/file.txt[/italic] --to japanese")
        eg_table.add_row("--to spanish  --gpu                    [dim]# Prefix is optional![/dim]")
        eg_table.add_row("[bold green]openbabelfish[/] --to french -o [italic]saved_translation.txt[/italic]")
        eg_table.add_row("[bold green]openbabelfish[/] --models                 [dim]# List all variants[/dim]")
        eg_table.add_row("[bold green]openbabelfish[/] --add-model 1.3B          [dim]# Download new variant[/dim]")
        eg_table.add_row("-m 1.3B -f [italic]file.txt[/italic] --to arabic --from english")
        console.print(Panel(eg_table, title="[bold bright_black]✦ Examples[/bold bright_black]", border_style="bright_black", expand=False, padding=(0, 1)))
        console.print()

        return ""


# ── FIRST‑RUN ONBOARDING ──────────────────────────────────────────────────────
def handle_first_run():
    console.clear()
    _print_logo()
    console.print(Panel(
        f"[bold bright_cyan]Welcome to OpenBabelFish![/]\n"
        f"[dim]Storage Location: [cyan]{BASE_DIR}[/][/dim]",
        box=box.DOUBLE_EDGE,
        border_style="cyan",
        expand=False,
        padding=(1, 4),
    ))
    console.print()

    # 1. GPU Detection
    dep_mgr = DependencyManager()
    is_gpu = False
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            console.print(Panel(
                f"[bold green]✓  NVIDIA GPU Detected[/]\n"
                f"[dim]Device: [cyan]{gpu_name}[/cyan][/dim]",
                border_style="green",
                expand=False,
                padding=(0, 2),
            ))
            if Confirm.ask("\n  Enable GPU acceleration? [dim](Downloads ~1.2 GB once)[/dim]", default=True):
                if dep_mgr.install_gpu_support():
                    is_gpu = True
                    console.print(Panel("[bold green]✓  GPU Acceleration Ready[/]", border_style="green", expand=False))
    except Exception:
        console.print("[dim]  No NVIDIA GPU detected — using CPU mode.[/dim]")
    
    console.print()

    # 2. Model Selection
    _print_divider("Select Your Model")
    model_mgr = ModelManager()
    variants = list(model_mgr.get_available_variants().keys())

    sel_table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, header_style="bold cyan", padding=(0, 2))
    sel_table.add_column("#", style="bold cyan", justify="center", width=3)
    sel_table.add_column("Variant", style="bold white")
    sel_table.add_column("Size & Description", style="dim")
    for i, v in enumerate(variants, 1):
        sel_table.add_row(str(i), v, VARIANT_INFO[v])
    console.print(Padding(sel_table, (1, 2)))

    idx = Prompt.ask("\n  [bold]Choose variant[/]", choices=[str(i) for i in range(1, len(variants)+1)], default="1")
    choice = variants[int(idx) - 1]
    console.print(f"\n  [green]✓[/] Selected: [bold cyan]{choice}[/]\n")

    model_mgr.download_model(choice)

    config = {
        "model_variant": choice,
        "model_path": str(get_model_path(choice).absolute()),
        "device": "cuda" if is_gpu else "cpu",
        "quantization": "int8"
    }
    save_config(config)
    console.print(Panel(
        "[bold green]✓  OpenBabelFish is ready![/]\n"
        "[dim]Your offline translation engine is configured and waiting.[/dim]",
        border_style="green",
        expand=False,
        padding=(1, 4),
    ))
    console.print()


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
    p.add_argument("--help", "-h", action="help" if not safe else "store_true")
    p.add_argument("text", nargs="*", help="Direct text to translate")
    return p


def _run_translation(args, config, model_mgr, dep_mgr):
    """Core translation logic extracted for reuse in CLI and REPL."""
    # Hardware switching (updates both local state and session config)
    current_device = config.get("device", "cpu")
    
    if args.gpu:
        if not dep_mgr.is_gpu_installed():
            console.print(Panel(
                "[yellow]CUDA libraries not found.[/]\n"
                "[dim]OpenBabelFish needs to download ~1.2 GB of NVIDIA runtimes.[/dim]",
                border_style="yellow", expand=False, padding=(0, 2)
            ))
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
        # We don't save_config here every time to avoid redundant writes, 
        # but we ensure model_path is tracked.

    model_status = model_mgr.get_model_status(model_variant)
    if model_status != "DOWNLOADED":
        status_label = "incomplete" if model_status == "INCOMPLETE" else "not downloaded"
        console.print(Panel(
            f"[yellow]Model '{model_variant}' is {status_label}.[/]",
            border_style="yellow", expand=False
        ))
        if Confirm.ask(f"  {'Fix' if model_status == 'INCOMPLETE' else 'Download'} {model_variant} now?"):
            model_mgr.download_model(model_variant)
        else:
            return

    # Input handling (File vs stdin vs arguments)
    text = ""
    if args.file:
        file_path = args.file.strip('"\'')
        try:
            text = Path(file_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            console.print(Panel(f"[red]File not found:[/] {file_path}", border_style="red", expand=False))
            return
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    elif hasattr(args, 'text') and args.text:
        text = " ".join(args.text)
    
    if not text.strip():
        # Check if we just did a hardware switch or model switch without text
        if args.gpu or args.cpu or args.model or args.add_model:
            hw_name = "⚡ CUDA (GPU)" if current_device == "cuda" else "⚙  CPU"
            console.print(f"\n  [bold green]✓[/] Mode set to [bold cyan]{hw_name}[/] (Model: [bold magenta]{model_variant}[/])\n")
            return

        # Otherwise show standard help/logo (but skip logo if in REPL session)
        is_repl = hasattr(sys, '_openbabelfish_repl') and sys._openbabelfish_repl
        if not is_repl:
            _print_logo()
        
        console.print(Panel(
            "[bold yellow]⚠  No input text detected.[/] \n\n"
            "[dim]Please use [cyan]--file path/to/file[/cyan] to translate a file,\n"
            "or type [cyan]--help[/cyan] to see available flags.\n\n"
            "[italic]Note: [cyan]--from[/cyan] is for the source language name (e.g. 'spanish'), not file paths.[/italic][/dim]",
            border_style="bright_black",
            expand=False,
            padding=(1, 4),
        ))
        return

    if not args.target_lang:
        console.print(Panel("[red]✗  Please specify a target language with [cyan]--to[/cyan][/red]", border_style="red", expand=False))
        return

    # Translation execution
    try:
        with console.status("[bold cyan]Initializing Engine...[/]", spinner="arc"):
            engine = TranslationEngine(model_path=str(model_path.absolute()), device=current_device)

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
        console.print(Panel(
            meta_table,
            title="[bold]🐡  OpenBabelFish[/bold]",
            subtitle="[dim]translation in progress…[/dim]",
            border_style="cyan",
            expand=False,
            padding=(1, 2),
        ))
        console.print()
        _print_divider("Output")
        console.print()

        result_chunks = []
        for chunk in engine.translate(text, args.target_lang, args.source_lang):
            result_chunks.append(chunk)
            console.print(chunk, end="", highlight=False)
        console.print("\n")

        if args.output:
            out_path = args.output.strip('"\'')
            Path(out_path).write_text("".join(result_chunks), encoding="utf-8")
            console.print(Panel(
                f"[green]✓  Saved to:[/] [cyan]{out_path}[/]",
                border_style="green",
                expand=False,
            ))
            console.print()

    except Exception as e:
        console.print(Panel(
            f"[bold red]✗  Translation Error[/]\n[dim]{e}[/dim]",
            border_style="red",
            expand=False,
            padding=(1, 2),
        ))


def interactive_shell():
    """High-fidelity interactive REPL using Rich."""
    # Mark the session so _run_translation knows we are in a REPL
    sys._openbabelfish_repl = True
    
    config = load_config()
    model_mgr = ModelManager()
    dep_mgr = DependencyManager()

    console.clear()
    _print_logo()
    
    # Session info
    active_model = config.get("model_variant", "None")
    active_device = config.get("device", "cpu").upper()
    
    console.print(Padding(
        Text.assemble(
            ("Session Active ", "bold bright_black"),
            (f"[{active_model}] ", "bold cyan"),
            (f"[{active_device}] ", "bold green"),
            (f"({BASE_DIR})", "dim italic")
        ),
        (0, 2)
    ))
    console.print(Padding("[dim]Type [cyan]exit[/] to quit. Use [cyan]--help[/] for options.[/dim]", (0, 2)))
    console.print()

    # Pre-configure parser for the REPL
    shell_parser = _build_parser(safe=True)

    while True:
        try:
            user_input = Prompt.ask(
                Text.assemble(("openbabelfish", "bold cyan"), (" ❯", "bold bright_black"))
            ).strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ["exit", "quit"]:
                console.print("[dim]Goodbye![/]")
                break
                
            if user_input.startswith("-"):
                # Parse as arguments
                try:
                    args = shell_parser.parse_args(shlex.split(user_input))
                    
                    if args.help:
                        OpenBabelFishHelpFormatter(shell_parser).format_help()
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

                    _run_translation(args, config, model_mgr, dep_mgr)
                except argparse.ArgumentError as e:
                    console.print(f"[bold red]Usage Error:[/] {e}")
                except Exception as e:
                    console.print(f"[bold red]Command Error:[/] {e}")
            else:
                # Direct text translation (Quick mode)
                # We need at least a target language. 
                # Check if it was prefixed with a lang like "spanish: Hello world"
                if ":" in user_input:
                    lang, text = user_input.split(":", 1)
                    args = shell_parser.parse_args(["--to", lang.strip()])
                    args.text = [text.strip()]
                    _run_translation(args, config, model_mgr, dep_mgr)
                else:
                    console.print("[yellow]⚠  Quick prompt requires a language. Try: [cyan]spanish: Hello[/cyan][/yellow]")

        except KeyboardInterrupt:
            console.print("\n[dim]Stopping session...[/]")
            break
        except Exception as e:
            console.print(f"[bold red]Shell Error:[/] {e}")


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

    console.print(Padding(t, (1, 2)))
    console.print(Padding(f"[dim]Library Path: [cyan]{BASE_DIR}[/][/dim]", (0, 2)))
    console.print(Padding("[dim]Use [cyan]--add-model[/cyan] to download more. Use [cyan]--model[/cyan] to switch.[/dim]", (0, 2)))
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

    console.print(Padding(t, (1, 2)))
    
    # Smart prompts based on what's missing
    if missing_core:
         console.print(Padding(f"[bold red]⚠ Critical Core packages are missing: {', '.join(missing_core)}[/]", (0, 2)))
         if Confirm.ask("  Install core requirements now?"):
             dep_mgr.install_missing(missing_core)
    
    if missing_gpu:
         console.print(Padding(f"[yellow]⚠ GPU Acceleration runtimes are missing: {', '.join(missing_gpu)}[/]", (0, 2)))
         if Confirm.ask("  Install NVIDIA GPU runtimes?"):
             dep_mgr.install_missing(missing_gpu)

    if not missing_core and not missing_gpu:
        console.print(Padding("[bold green]✓ Complete system audit passed. All modules synchronized.[/]", (0, 2)))
    console.print()


def main():
    # Standard CLI Mode
    parser = _build_parser(safe=False)
    # If no arguments are passed, enter interactive mode
    if len(sys.argv) == 1:
        interactive_shell()
        return

    args = parser.parse_args()
    
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

    # Priority 3: Setup and Downloads
    if not is_setup_complete() and not args.add_model:
        handle_first_run()
        config = load_config()

    if args.add_model:
        _print_divider(f"Downloading {args.add_model}")
        model_mgr.download_model(args.add_model)
        return

    # Standard translation workflow
    _run_translation(args, config, model_mgr, dep_mgr)



if __name__ == "__main__":
    main()
