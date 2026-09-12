from lingua import Language, LanguageDetectorBuilder

try:
    from langdetect import detect as langdetect_detect
except ImportError:
    langdetect_detect = None


# ============================================================
# SUPPORTED LANGUAGES
# ============================================================

LANGUAGES = [
    Language.ENGLISH,
    Language.TURKISH,
    Language.ITALIAN,
    Language.JAPANESE,
    Language.GERMAN,
    Language.FRENCH,
    Language.SPANISH,
    Language.PORTUGUESE,
]


detector = (
    LanguageDetectorBuilder
    .from_languages(*LANGUAGES)
    .with_preloaded_language_models()
    .build()
)


LANGUAGE_NAMES = {
    Language.ENGLISH: "English",
    Language.TURKISH: "Turkish",
    Language.ITALIAN: "Italian",
    Language.JAPANESE: "Japanese",
    Language.GERMAN: "German",
    Language.FRENCH: "French",
    Language.SPANISH: "Spanish",
    Language.PORTUGUESE: "Portuguese",
}


# ============================================================
# SCRIPT DETECTION
# ============================================================

def detect_script(text: str):

    for char in text:
        code = ord(char)

        # Hiragana
        if 0x3040 <= code <= 0x309F:
            return "Japanese"

        # Katakana
        if 0x30A0 <= code <= 0x30FF:
            return "Japanese"

        # Kanji
        if 0x4E00 <= code <= 0x9FFF:
            return "Japanese"

        # Korean
        if 0xAC00 <= code <= 0xD7AF:
            return "Korean"

    return None


# ============================================================
# LANGDETECT → OUR LANGUAGE NAMES
# ============================================================

LANGDETECT_MAP = {
    "en": "English",
    "tr": "Turkish",
    "it": "Italian",
    "ja": "Japanese",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
}


def secondary_detect(text: str):

    if langdetect_detect is None:
        return None

    try:
        result = langdetect_detect(text)

        return LANGDETECT_MAP.get(result)

    except Exception:
        return None


# ============================================================
# MAIN LANGUAGE DETECTOR
# ============================================================

def detect_language(text: str) -> str:

    text = text.strip()

    if not text:
        return "English"

    # --------------------------------------------------------
    # 1. Writing system
    # --------------------------------------------------------

    script_language = detect_script(text)

    if script_language:
        return script_language

    # --------------------------------------------------------
    # 2. Very short input
    # --------------------------------------------------------

    letters = [
        c for c in text
        if c.isalpha()
    ]

    if len(letters) < 8:
        return "English"

    # --------------------------------------------------------
    # 3. Lingua
    # --------------------------------------------------------

    lingua_language = None

    try:

        result = detector.detect_language_of(text)

        if result is not None:
            lingua_language = LANGUAGE_NAMES.get(result)

    except Exception:
        pass

    # --------------------------------------------------------
    # 4. Confidence analysis
    # --------------------------------------------------------

    best_score = 0.0
    english_score = 0.0

    try:

        values = detector.compute_language_confidence_values(text)

        values = sorted(
            values,
            key=lambda x: x.value,
            reverse=True
        )

        if values:

            best_score = values[0].value

            for item in values:

                if item.language == Language.ENGLISH:
                    english_score = item.value
                    break

    except Exception:
        pass

    # --------------------------------------------------------
    # 5. Secondary detector
    # --------------------------------------------------------

    secondary_language = secondary_detect(text)

    # --------------------------------------------------------
    # 6. Agreement between detectors
    #
    # If both models agree, trust them.
    # --------------------------------------------------------

    if (
        lingua_language is not None
        and secondary_language is not None
        and lingua_language == secondary_language
    ):
        return lingua_language

    # --------------------------------------------------------
    # 7. Strong Lingua result
    # --------------------------------------------------------

    if lingua_language is not None:

        margin = best_score - english_score

        if best_score >= 0.45 and margin >= 0.06:
            return lingua_language

    # --------------------------------------------------------
    # 8. Secondary detector result
    #
    # Particularly useful for short Latin-script sentences.
    # --------------------------------------------------------

    if secondary_language is not None:

        if secondary_language != "English":

            return secondary_language

    # --------------------------------------------------------
    # 9. Lingua fallback
    # --------------------------------------------------------

    if lingua_language is not None:
        return lingua_language

    # --------------------------------------------------------
    # 10. DEFAULT
    # --------------------------------------------------------

    return "English"