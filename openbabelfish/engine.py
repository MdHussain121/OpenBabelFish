import os
import sys
import ctranslate2
import transformers
import langid
import re
from pathlib import Path
from typing import Iterator, Optional
from .config import load_config, get_model_path

# Mappings for common names to FLORES-200 codes
# This is a partial list for convenience; users can also pass codes directly.
LANG_MAP = {
    "acehnese": "ace_Latn",
    "acehnese (arabic script)": "ace_Arab",
    "acehnese (latin script)": "ace_Latn",
    "acehnese arabic script": "ace_Arab",
    "acehnese latin script": "ace_Latn",
    "acholi": "ach_Latn",
    "afar": "aar_Latn",
    "afrikaans": "afr_Latn",
    "akan": "aka_Latn",
    "amharic": "amh_Ethi",
    "arabic": "arb_Arab",
    "arabic (egyptian)": "arz_Arab",
    "arabic (mesopotamian)": "acm_Arab",
    "arabic (moroccan)": "ary_Arab",
    "arabic (najdi)": "ars_Arab",
    "arabic (north levantine)": "apc_Arab",
    "arabic (south levantine)": "ajp_Arab",
    "arabic (standard)": "arb_Arab",
    "arabic (ta'izzi-adeni)": "acq_Arab",
    "arabic (tunisian)": "aeb_Arab",
    "arabic egyptian": "arz_Arab",
    "arabic mesopotamian": "acm_Arab",
    "arabic moroccan": "ary_Arab",
    "arabic najdi": "ars_Arab",
    "arabic north levantine": "apc_Arab",
    "arabic south levantine": "ajp_Arab",
    "arabic standard": "arb_Arab",
    "arabic ta'izzi-adeni": "acq_Arab",
    "arabic tunisian": "aeb_Arab",
    "armenian": "hye_Armn",
    "assamese": "asm_Beng",
    "asturian": "ast_Latn",
    "aymara": "ayr_Latn",
    "aymara (central)": "ayr_Latn",
    "aymara central": "ayr_Latn",
    "azerbaijani": "azj_Latn",
    "azerbaijani (north)": "azj_Latn",
    "azerbaijani (south)": "azb_Arab",
    "azerbaijani north": "azj_Latn",
    "azerbaijani south": "azb_Arab",
    "balinese": "ban_Latn",
    "bambara": "bam_Latn",
    "bangla": "ben_Beng",
    "bashkir": "bak_Cyrl",
    "basque": "eus_Latn",
    "belarusian": "bel_Cyrl",
    "bemba": "bem_Latn",
    "bhojpuri": "bho_Deva",
    "bikol": "bcl_Latn",
    "bikol (central)": "bcl_Latn",
    "bikol central": "bcl_Latn",
    "bosnian": "bos_Latn",
    "buginese": "bug_Latn",
    "bulgarian": "bul_Cyrl",
    "burmese": "mya_Mymr",
    "catalan": "cat_Latn",
    "cebuano": "ceb_Latn",
    "chhattisgarhi": "hne_Deva",
    "chinese": "zho_Hans",
    "chinese (simplified)": "zho_Hans",
    "chinese (traditional)": "zho_Hant",
    "chinese simplified": "zho_Hans",
    "chinese traditional": "zho_Hant",
    "chokwe": "cjk_Latn",
    "crimean tatar": "crh_Latn",
    "croatian": "hrv_Latn",
    "czech": "ces_Latn",
    "danish": "dan_Latn",
    "dinka": "dik_Latn",
    "dinka (southwestern)": "dik_Latn",
    "dinka southwestern": "dik_Latn",
    "dutch": "nld_Latn",
    "dyula": "dyu_Latn",
    "dzongkha": "dzo_Tibt",
    "english": "eng_Latn",
    "esperanto": "epo_Latn",
    "estonian": "est_Latn",
    "ewe": "ewe_Latn",
    "faroese": "fao_Latn",
    "fijian": "fij_Latn",
    "finnish": "fin_Latn",
    "fon": "fon_Latn",
    "french": "fra_Latn",
    "friulian": "fur_Latn",
    "fulfulde": "fuv_Latn",
    "fulfulde (nigerian)": "fuv_Latn",
    "fulfulde nigerian": "fuv_Latn",
    "gaelic": "gla_Latn",
    "gaelic (scottish)": "gla_Latn",
    "gaelic scottish": "gla_Latn",
    "galician": "glg_Latn",
    "ganda": "lug_Latn",
    "georgian": "kat_Geor",
    "german": "deu_Latn",
    "greek": "ell_Grek",
    "guarani": "grn_Latn",
    "gujarati": "guj_Gujr",
    "haitian creole": "hat_Latn",
    "hausa": "hau_Latn",
    "hebrew": "heb_Hebr",
    "hindi": "hin_Deva",
    "hungarian": "hun_Latn",
    "icelandic": "isl_Latn",
    "igbo": "ibo_Latn",
    "ilocano": "ilo_Latn",
    "indonesian": "ind_Latn",
    "irish": "gle_Latn",
    "italian": "ita_Latn",
    "japanese": "jpn_Jpan",
    "javanese": "jav_Latn",
    "kabyle": "kab_Latn",
    "kachin": "kac_Latn",
    "kamba": "kam_Latn",
    "kannada": "kan_Knda",
    "kanuri": "knc_Latn",
    "kanuri (central)": "knc_Latn",
    "kanuri central": "knc_Latn",
    "kazakh": "kaz_Cyrl",
    "khmer": "khm_Khmr",
    "kimbundu": "kmb_Latn",
    "kinyarwanda": "kin_Latn",
    "kirundi": "run_Latn",
    "korean": "kor_Hang",
    "kurdish": "ckb_Arab",
    "kurdish (central)": "ckb_Arab",
    "kurdish (northern)": "kmr_Latn",
    "kurdish central": "ckb_Arab",
    "kurdish northern": "kmr_Latn",
    "kyrgyz": "kir_Cyrl",
    "lao": "lao_Laoo",
    "latvian": "lvs_Latn",
    "ligurian": "lij_Latn",
    "lingala": "lin_Latn",
    "lithuanian": "lit_Latn",
    "lombard": "lmo_Latn",
    "luo": "luo_Latn",
    "luxembourgish": "ltz_Latn",
    "macedonian": "mkd_Cyrl",
    "magahi": "mag_Deva",
    "maithili": "mai_Deva",
    "malagasy": "mlg_Latn",
    "malay": "zsm_Latn",
    "malay (indonesian)": "zsm_Latn",
    "malay indonesian": "zsm_Latn",
    "malayalam": "mal_Mlym",
    "maltese": "mlt_Latn",
    "manipuri": "mni_Beng",
    "marathi": "mar_Deva",
    "minangkabau": "min_Latn",
    "mizo": "lus_Latn",
    "mongolian": "mon_Cyrl",
    "mossi": "mos_Latn",
    "nepali": "npi_Deva",
    "nuer": "nus_Latn",
    "nyanja": "nya_Latn",
    "occitan": "oci_Latn",
    "odia": "ory_Orya",
    "oromo": "gaz_Latn",
    "oromo (afaan)": "gaz_Latn",
    "oromo afaan": "gaz_Latn",
    "pangasinan": "pag_Latn",
    "pashto": "pbt_Arab",
    "persian": "prs_Arab",
    "persian (eastern)": "prs_Arab",
    "persian (western)": "pes_Arab",
    "persian eastern": "prs_Arab",
    "persian western": "pes_Arab",
    "polish": "pol_Latn",
    "portuguese": "por_Latn",
    "punjabi": "pan_Guru",
    "punjabi (eastern)": "pan_Guru",
    "punjabi eastern": "pan_Guru",
    "quechua": "quy_Latn",
    "quechua (south)": "quy_Latn",
    "quechua south": "quy_Latn",
    "romanian": "ron_Latn",
    "rundi": "run_Latn",
    "russian": "rus_Cyrl",
    "samoan": "smo_Latn",
    "sanskrit": "san_Deva",
    "santali": "sat_Olck",
    "sardinian": "srd_Latn",
    "serbian": "srp_Cyrl",
    "shan": "shn_Mymr",
    "shona": "sna_Latn",
    "sicilian": "scn_Latn",
    "sindhi": "snd_Arab",
    "sinhala": "sin_Sinh",
    "slovak": "slk_Latn",
    "slovenian": "slv_Latn",
    "somali": "som_Latn",
    "sotho": "nso_Latn",
    "sotho (northern)": "nso_Latn",
    "sotho (southern)": "sot_Latn",
    "sotho northern": "nso_Latn",
    "sotho southern": "sot_Latn",
    "spanish": "spa_Latn",
    "sundanese": "sun_Latn",
    "swahili": "swh_Latn",
    "swati": "ssw_Latn",
    "swedish": "swe_Latn",
    "tagalog": "tgl_Latn",
    "tajik": "tgk_Cyrl",
    "tamasheq": "taq_Latn",
    "tamil": "tam_Taml",
    "tatar": "tat_Cyrl",
    "telugu": "tel_Telu",
    "thai": "tha_Thai",
    "tibetan": "bod_Tibt",
    "tibetan (standard)": "bod_Tibt",
    "tibetan standard": "bod_Tibt",
    "tigrinya": "tir_Ethi",
    "tok pisin": "tpi_Latn",
    "tsonga": "tso_Latn",
    "tswana": "tsn_Latn",
    "turkish": "tur_Latn",
    "turkmen": "tuk_Latn",
    "twi": "twi_Latn",
    "ukrainian": "ukr_Cyrl",
    "umbundu": "umb_Latn",
    "urdu": "urd_Arab",
    "uzbek": "uzn_Latn",
    "vietnamese": "vie_Latn",
    "waray": "war_Latn",
    "welsh": "cym_Latn",
    "wolof": "wol_Latn",
    "xhosa": "xho_Latn",
    "yiddish": "yid_Hebr",
    "yoruba": "yor_Latn",
    "zulu": "zul_Latn"
}


class TranslationEngine:
    def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None):
        config = load_config()
        self.model_variant = config.get("model_variant", "unknown")
        # Preference: Argument > Config > Default
        self.model_path = model_path or config.get("model_path")
        self.device = device or config.get("device", "cpu")
        self.quantization = config.get("quantization", "int8")
        
        self._translator = None
        self._tokenizer = None

    def reload(self, model_path: Optional[str] = None, device: Optional[str] = None):
        """Re-initialize the translator and tokenizer with new settings."""
        if model_path:
            self.model_path = model_path
        if device:
            self.device = device
            
        self._translator = None
        self._tokenizer = None
        # Force immediate load to verify
        _ = self.translator

    def _setup_cuda_dlls(self):
        """Register NVIDIA CUDA DLL directories to the OS search path on Windows."""
        if sys.platform != "win32" or self.device != "cuda":
            return

        # Locate the virtual environment's site-packages
        for path in sys.path:
            if "site-packages" in path:
                nvidia_base = Path(path) / "nvidia"
                if nvidia_base.exists():
                    # Find all 'bin' directories within nvidia subpackages
                    for bin_dir in nvidia_base.glob("*/bin"):
                        if bin_dir.is_dir():
                            try:
                                os.add_dll_directory(str(bin_dir.absolute()))
                            except Exception:
                                pass
        
    @property
    def translator(self):
        if self._translator is None:
            if not self.model_path or not os.path.exists(self.model_path):
                raise RuntimeError("Model path not configured or missing. Run setup first.")
            
            # Ensure CUDA DLLs are visible to the OS loader on Windows
            self._setup_cuda_dlls()
            
            self._translator = ctranslate2.Translator(
                self.model_path,
                device=self.device,
                compute_type=self.quantization
            )
        return self._translator

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            # We use the tokenizer from transformers since it's compatible with NLLB-200
            # Path should be the same as the model path
            self._tokenizer = transformers.AutoTokenizer.from_pretrained(self.model_path)
        return self._tokenizer

    def _resolve_lang_code(self, lang: str) -> str:
        """Resolve a language name or code to a FLORES-200 code."""
        lang = lang.lower()
        if lang in LANG_MAP:
            return LANG_MAP[lang]
        # If it looks like an NLLB code already (3 chars + _ + 4 chars), return it
        if "_" in lang and len(lang) >= 8:
            return lang
        return lang

    def detect_language(self, text: str) -> str:
        """Detect language using langid."""
        try:
            # langid returns (code, confidence)
            lang, _ = langid.classify(text)
            return lang
        except Exception:
            return "unknown"

    def _get_chunks(self, text: str) -> Iterator[str]:
        """Split text into manageable chunks (paragraphs and sentences)."""
        # We handle splitting logically in the translate method to respect structure
        return iter(text.split("\n\n"))

    def translate(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> Iterator[str]:
        """Translate text using CTranslate2 with chunking support."""
        if not source_lang:
            source_lang = self.detect_language(text)
            
        tgt_code = self._resolve_lang_code(target_lang)
        src_code = self._resolve_lang_code(source_lang)

        # Process paragraph by paragraph to respect original structure
        paragraphs = text.split("\n\n")
        
        for i, para in enumerate(paragraphs):
            if not para.strip():
                continue
                
            # If paragraph is very long, split into sentences for model safety
            if len(para) > 1000:
                sub_chunks = [s.strip() for s in re.split(r'(?<=[.!?])\s+', para) if s.strip()]
            else:
                sub_chunks = [para.strip()]

            # Translate sub-chunks (sentences) in a batch
            batch_source_tokens = []
            for chunk_text in sub_chunks:
                tokens = self.tokenizer.convert_ids_to_tokens(self.tokenizer.encode(chunk_text))
                if tokens[-1] != src_code:
                    if tokens[-1] == "</s>":
                        tokens.append(src_code)
                    else:
                        tokens.extend(["</s>", src_code])
                batch_source_tokens.append(tokens)

            target_prefixes = [[tgt_code]] * len(sub_chunks)
            filter_tokens = {"<unk>", "</s>", "<s>", "<pad>"}
            filter_tokens.update(LANG_MAP.values())

            results = self.translator.translate_batch(
                batch_source_tokens,
                target_prefix=target_prefixes,
                beam_size=2,
                max_decoding_length=512,
            )
            
            translated_sub_chunks = []
            for result in results:
                output_tokens = result.hypotheses[0]
                if output_tokens[0] == tgt_code:
                    output_tokens = output_tokens[1:]
                
                clean_tokens = [t for t in output_tokens if t not in filter_tokens]
                translated_sub_chunks.append(self.tokenizer.decode(self.tokenizer.convert_tokens_to_ids(clean_tokens)))
            
            # Combine sentences into a paragraph and yield
            yield " ".join(translated_sub_chunks)
            
            # Add paragraph separation if not the last one
            if i < len(paragraphs) - 1:
                yield "\n\n"
