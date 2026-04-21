import re
import pandas as pd


# ── Column type detection ──────────────────────────────────────────────────────

COLUMN_NAME_MAP = {
    'address': ['adresse', 'address', 'rue', 'voie'],
    'postal_code': ['code_postal', 'postal_code', 'cp', 'zip'],
    'city': ['ville', 'city', 'commune'],
    'phone': ['telephone', 'phone', 'tel', 'mobile', 'portable'],
    'email': ['email', 'mail', 'courriel'],
    'siret': ['siret'],
    'siren': ['siren'],
}

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
PHONE_RE = re.compile(r'^[\d\s\.\-\+\(\)]{7,20}$')
SIRET_RE = re.compile(r'^\d{14}$')
SIREN_RE = re.compile(r'^\d{9}$')
POSTAL_RE = re.compile(r'^\d{4,5}$')


def detect_column_type(series: pd.Series, col_name: str = '') -> str:
    name = col_name.lower().strip()
    for col_type, keywords in COLUMN_NAME_MAP.items():
        if any(kw in name for kw in keywords):
            return col_type

    # Fallback: pattern matching on sample values
    sample = series.dropna().astype(str).head(20)
    if sample.empty:
        return 'text'

    def pct_match(pattern):
        return sample.apply(lambda v: bool(pattern.match(v.strip()))).mean()

    scores = {
        'email': pct_match(EMAIL_RE),
        'siret': sample.apply(lambda v: bool(SIRET_RE.match(re.sub(r'\s', '', v)))).mean(),
        'siren': sample.apply(lambda v: bool(SIREN_RE.match(re.sub(r'\s', '', v)))).mean(),
        'postal_code': sample.apply(lambda v: bool(POSTAL_RE.match(v.strip()))).mean(),
        'phone': pct_match(PHONE_RE),
    }
    best = max(scores, key=scores.get)
    if scores[best] >= 0.5:
        return best
    return 'text'


# ── Normalizers ────────────────────────────────────────────────────────────────

ABBREV_MAP = {
    r'\brue\b': 'Rue',
    r'\bav\b': 'Avenue',
    r'\bavenue\b': 'Avenue',
    r'\bbd\b': 'Boulevard',
    r'\bboulevard\b': 'Boulevard',
    r'\bimpr?\b': 'Impasse',
    r'\bpl\b': 'Place',
    r'\balle?e?\b': 'Allée',
}


def normalize_address(val):
    if pd.isna(val):
        return val
    s = str(val).strip()
    for pattern, replacement in ABBREV_MAP.items():
        s = re.sub(pattern, replacement, s, flags=re.IGNORECASE)
    # Title-case each word, but preserve already-fixed abbreviations
    parts = s.split()
    result = ' '.join(w if w in ('Rue', 'Avenue', 'Boulevard', 'Impasse', 'Place', 'Allée')
                      else w.title() for w in parts)
    return re.sub(r'\s+', ' ', result)


def normalize_postal_code(val):
    if pd.isna(val):
        return val
    digits = re.sub(r'\D', '', str(val))
    if len(digits) == 4:
        digits = '0' + digits
    return digits


def normalize_city(val):
    if pd.isna(val):
        return val
    return str(val).strip().upper()


def normalize_phone(val):
    if pd.isna(val):
        return val
    s = re.sub(r'[\s\.\-\(\)]', '', str(val))
    if s.startswith('+33'):
        s = '0' + s[3:]
    digits = re.sub(r'\D', '', s)
    if len(digits) == 10:
        return ' '.join([digits[i:i+2] for i in range(0, 10, 2)])
    return val


def normalize_email(val):
    if pd.isna(val):
        return val
    return str(val).strip().lower()


def normalize_siret(val):
    if pd.isna(val):
        return val
    digits = re.sub(r'\s', '', str(val))
    if len(digits) == 14:
        return f"{digits[:3]} {digits[3:6]} {digits[6:9]} {digits[9:]}"
    return val


def normalize_siren(val):
    if pd.isna(val):
        return val
    digits = re.sub(r'\s', '', str(val))
    if len(digits) == 9:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    return val


NORMALIZERS = {
    'address': normalize_address,
    'postal_code': normalize_postal_code,
    'city': normalize_city,
    'phone': normalize_phone,
    'email': normalize_email,
    'siret': normalize_siret,
    'siren': normalize_siren,
    'text': lambda v: v,
}


# ── Validators for scoring ─────────────────────────────────────────────────────

def is_valid_email(v):
    return bool(EMAIL_RE.match(str(v).strip()))


def is_valid_phone(v):
    digits = re.sub(r'\D', '', str(v))
    return len(digits) == 10


def is_valid_postal(v):
    return bool(re.match(r'^\d{5}$', str(v).strip()))


def is_valid_siret(v):
    return bool(re.match(r'^\d{3} \d{3} \d{3} \d{5}$', str(v).strip()))


def is_valid_siren(v):
    return bool(re.match(r'^\d{3} \d{3} \d{3}$', str(v).strip()))


VALIDATORS = {
    'email': is_valid_email,
    'phone': is_valid_phone,
    'postal_code': is_valid_postal,
    'siret': is_valid_siret,
    'siren': is_valid_siren,
    'address': lambda v: len(str(v).strip()) > 3,
    'city': lambda v: len(str(v).strip()) > 1,
    'text': lambda v: len(str(v).strip()) > 0,
}


# ── Scoring ────────────────────────────────────────────────────────────────────

def score_column(series: pd.Series, col_type: str) -> dict:
    total = len(series)
    if total == 0:
        return {'completeness': 0, 'validity': 0, 'uniqueness': 0, 'score': 0,
                'missing_count': 0, 'invalid_count': 0, 'duplicate_count': 0}

    # Completeness
    missing = series.isna() | (series.astype(str).str.strip() == '')
    missing_count = int(missing.sum())
    completeness = round((1 - missing_count / total) * 100, 1)

    # Validity
    non_missing = series[~missing]
    validator = VALIDATORS.get(col_type, VALIDATORS['text'])
    if len(non_missing) > 0:
        invalid_count = int((~non_missing.apply(lambda v: validator(v))).sum())
    else:
        invalid_count = 0
    validity = round(((len(non_missing) - invalid_count) / total) * 100, 1)

    # Uniqueness
    duplicate_count = int(series.duplicated(keep=False).sum())
    uniqueness = round((1 - duplicate_count / total) * 100, 1) if total > 0 else 100.0

    score = round(completeness * 0.4 + validity * 0.4 + uniqueness * 0.2, 1)

    return {
        'completeness': completeness,
        'validity': validity,
        'uniqueness': uniqueness,
        'score': score,
        'missing_count': missing_count,
        'invalid_count': invalid_count,
        'duplicate_count': duplicate_count,
    }


# ── Main pipeline ──────────────────────────────────────────────────────────────

def clean_dataframe(df: pd.DataFrame) -> dict:
    rows_before = len(df)

    # Detect column types
    col_types = {col: detect_column_type(df[col], col) for col in df.columns}

    # Score before cleaning
    col_scores_before = {col: score_column(df[col], col_types[col]) for col in df.columns}
    global_score_before = round(
        sum(s['score'] for s in col_scores_before.values()) / len(col_scores_before), 1
    ) if col_scores_before else 0

    changes_log = []

    # Remove exact duplicates
    df_clean = df.drop_duplicates()
    removed_dupes = rows_before - len(df_clean)
    if removed_dupes:
        changes_log.append(f"{removed_dupes} ligne(s) dupliquée(s) supprimée(s)")

    # Apply normalizers
    df_clean = df_clean.copy()
    for col in df_clean.columns:
        col_type = col_types[col]
        normalizer = NORMALIZERS.get(col_type, NORMALIZERS['text'])
        original = df_clean[col].copy()
        df_clean[col] = df_clean[col].astype(object)
        df_clean.loc[:, col] = df_clean[col].apply(normalizer)
        changed = (df_clean[col].astype(str) != original.astype(str)).sum()
        if changed:
            changes_log.append(
                f"Colonne '{col}' ({col_type}): {changed} valeur(s) normalisée(s)"
            )

    rows_after = len(df_clean)

    # Score after cleaning
    col_scores_after = {col: score_column(df_clean[col], col_types[col]) for col in df_clean.columns}
    global_score_after = round(
        sum(s['score'] for s in col_scores_after.values()) / len(col_scores_after), 1
    ) if col_scores_after else 0

    return {
        'df_clean': df_clean,
        'col_types': col_types,
        'col_scores_before': col_scores_before,
        'col_scores_after': col_scores_after,
        'global_score_before': global_score_before,
        'global_score_after': global_score_after,
        'changes_log': changes_log,
        'rows_before': rows_before,
        'rows_after': rows_after,
    }
