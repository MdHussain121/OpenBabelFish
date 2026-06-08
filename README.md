# 🐡 OpenBabelFish

A high-performance, fully-offline translation appliance. **OpenBabelFish** is designed for users who need professional-grade translation without compromising privacy or relying on cloud providers.

![OpenBabelFish CLI](https://img.shields.io/badge/Interface-Rich--CLI-brightgreen)
![Engine](https://img.shields.io/badge/Engine-CTranslate2-blue)
![Model](https://img.shields.io/badge/Model-NLLB--200-orange)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🚀 Key Features

- **Local-First & Private**: Complete offline translation. No internet connection is used or required once models are downloaded.
- **Deep Translation Engine**: Powered by Meta's NLLB-200 (No Language Left Behind) models.
- **Multi-Format Document Extraction**: Translates complex document layouts natively. Supported files:
  - 📄 **PDF (`.pdf`)**: Direct text extraction, with automatic fallback to OCR for scanned documents.
  - 📝 **Word (`.docx`)**: Extract paragraphs in sequence.
  - 📊 **PowerPoint (`.pptx`)**: Extract slide text.
  - 📚 **EPUB (`.epub`)**: Strip HTML tags and read chapter pages.
  - 🗂 **Plain Text (`.txt`)**: Standard text processing.
- **Smart OCR Engine**: Integrated EasyOCR engine with automatic heuristic page-density checking (falls back to OCR if a PDF is scanned). Bypasses directly with `--ocr` and runs on CPU or GPU.
- **Flexible Language Resolution**: Supports standard language names (e.g., `english`, `spanish`), FLORES-200 language codes (e.g., `eng_Latn`, `spa_Latn`), and **2-letter ISO 639-1 language codes** (e.g., `en`, `es`, `fr`, `ja`).
- **Hardware Optimized**: Supports seamless switching between CPU and NVIDIA GPU (CUDA) acceleration with automatic dependency auditing.
- **Smart Model Management**: Automatically downloads, validates, and manages model variants (600M, 1.3B, 3.3B) with leak-proof system hooks.
- **On-Demand Dependency Auditing**: Dynamic checks prompt you to download missing dependencies (such as PDF readers or OCR tools) right when you try to open that file type, showing real-time download progress in MB.
- **Cross-Platform Compatibility**: Enhanced terminal Unicode/UTF-8 output configuration, ensuring crashes are prevented on Windows systems.
- **Interactive REPL**: A beautiful, colorized shell interface for real-time translation, config management, and quick inline execution.

## 🛠 Installation

### Prerequisites
- Python 3.10+
- (Optional) NVIDIA GPU for CUDA acceleration

### Quick Start
1. Clone the repository:
   ```bash
   git clone https://github.com/MdHussain121/OpenBabelFish.git
   cd OpenBabelFish
   ```
2. Run the automated launcher:
   ```bash
   run_openbabelfish.bat
   ```
   *The launcher will automatically create a virtual environment, install dependencies, and guide you through the first-run configuration.*

## 💻 Usage

### Command Line Mode
```bash
# Translate a text file
openbabelfish --to es -f document.txt

# Translate a Word document
openbabelfish --to french -f report.docx

# Translate a scanned PDF forcing OCR on GPU
openbabelfish --to japanese -f scanned_doc.pdf --ocr --ocr-device gpu
```

### Options
- `--to [lang]`: Target language (Required; accepts names like `spanish`, ISO codes like `es`, or FLORES codes like `spa_Latn`)
- `--from [lang]`: Source language (Auto-detected if omitted)
- `-f, --file [path]`: Read input from a local file (`.txt`, `.pdf`, `.docx`, `.pptx`, `.epub`)
- `-o, --output [path]`: Save translation to a file
- `--gpu / --cpu`: Force specific hardware mode
- `--ocr`: Force OCR on PDF files (skips text layer extraction)
- `--ocr-device [cpu|gpu]`: Set device for OCR execution
- `--models`: Show and manage downloaded model variants
- `--packages`: Audit system dependencies and install missing requirements

### Interactive Shell
Simply run `openbabelfish` (or `run_openbabelfish.bat`) with no arguments to enter the interactive shell.

#### Quick translation in REPL
In the REPL, you can translate inline using prefix notation:
```text
openbabelfish ❯ spanish: Hello world
openbabelfish ❯ es: How are you?
openbabelfish ❯ read document.pdf to es
openbabelfish ❯ file slide.pptx target french
```

## 📜 License
This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments
- **Meta AI** for the NLLB-200 models.
- **OpenNMT** for the CTranslate2 inference engine.
- **Rich** for the stunning terminal UI components.
- **Jaided AI** for the EasyOCR engine.
