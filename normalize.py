"""
normalize.py — Unicode/Turkish character normalization for search and indexing.
Converts Turkish special characters to ASCII equivalents.
"""

import unicodedata
import re

# Turkish-specific character mappings
_TR_MAP = str.maketrans({
    'ç': 'c', 'Ç': 'C',
    'ğ': 'g', 'Ğ': 'G',
    'ı': 'i', 'İ': 'I',
    'ö': 'o', 'Ö': 'O',
    'ş': 's', 'Ş': 'S',
    'ü': 'u', 'Ü': 'U',
    # Common accented chars from other languages
    'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a',
    'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
    'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
    'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o',
    'ù': 'u', 'ú': 'u', 'û': 'u',
    'ñ': 'n', 'ý': 'y', 'ÿ': 'y',
})


def normalize_text(text):
    """Normalize text: Turkish chars → ASCII, lowercase, strip."""
    if not text:
        return ""
    # Apply Turkish mappings first
    result = text.translate(_TR_MAP)
    # Fallback: strip remaining accents via unicode decomposition
    result = unicodedata.normalize('NFD', result)
    result = ''.join(c for c in result if unicodedata.category(c) != 'Mn')
    return result.lower()


def tokenize(text):
    """Tokenize text into normalized lowercase ASCII words (2+ chars)."""
    normalized = normalize_text(text)
    return re.findall(r'[a-zA-Z]{2,}', normalized)
