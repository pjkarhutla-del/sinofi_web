"""Utilitas normalisasi nama pulau (port dari canonicalPulau di aplikasi lama)."""
import re

PULAU_LIST = ["SUMATERA", "KALIMANTAN", "JAWA", "BALI NUSRA", "SULAWESI", "MALUKU", "PAPUA"]

_RULES = [
    ("SUMATERA", r"SUMATERA|ACEH|RIAU|JAMBI|BENGKULU|LAMPUNG|SUMUT|SUMSEL|SUMBAR"),
    ("KALIMANTAN", r"KALIMANTAN|KALBAR|KALTENG|KALSEL|KALTIM|KALTARA"),
    ("JAWA", r"JAWA|JABAR|JATENG|JATIM|BANTEN|DKI|YOGYA"),
    ("BALI NUSRA", r"BALI|NUSRA|NTB|NTT|JABALNUSRA"),
    ("SULAWESI", r"SULAWESI|SULSEL|SULBAR|SULTENG|SULTRA|SULUT|GORONTALO"),
]


def canonical_pulau(value=""):
    x = re.sub(r"\s+", " ", re.sub(r"[-_]+", " ", str(value or "").strip().upper()))
    for name, pattern in _RULES:
        if re.search(pattern, x):
            return name
    if "MALUKU" in x and "PAPUA" not in x:
        return "MALUKU"
    if "PAPUA" in x:
        return "PAPUA"
    return "LAINNYA"


def norm_text(value=""):
    """Normalisasi untuk pencocokan nama: trim, huruf besar, spasi tunggal."""
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()
