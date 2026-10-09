"""Versioned text normalization with general rules and occurrence-level spans.

Policy is not spell correction. Never expand numbers/abbreviations, translate,
remove negation or guess what a model intended. Optional reviewed equivalences
are explicit, versioned and off by default. See docs/NORMALIZATION_POLICY.md.
"""
import html
import re
import unicodedata as ud
from .orthography import apply_reviewed_variants, VARIANTS_ID

from .rule_based import (RULE_DEFAULTS, fold_character, fold_arabic_joiners,
                         apply_suffix_rules, is_arabic_vowel)

NORMALIZER_VERSION = '1.3.0'
DEFAULT_PROFILE = {
    'language': 'mixed', 'diacritics': True, 'alif': True, 'tatweel': True,
    'digits': True, 'punctuation': True, 'lowercase': False, 'cer_spaces': True,
    'arabic_spelling': False, 'arabic_question_forms': False,
    **RULE_DEFAULTS,
}
DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
ALIF = str.maketrans({c: 'ا' for c in 'أإآٱٲٳٵ'})
# Remove display-only controls, NOT all Cf characters (joiners can be meaningful).
DISPLAY_CONTROLS = set('\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u2060\ufeff\u00ad')
# Conservative case handling. Preserve recognized unit families in ANY spelling.
PROTECTED = re.compile(r'(?<!\w)(?:ml|dl|ul|µl|μl|l|iu|u|miu|kiu|pa|kpa|hpa|mpa|mmhg|ph|v|mv|w|kw|mg|g|kg|mcg|ug|µg|μg|ng|pg|mol|mmol|nmol|mm|cm|m|km|hz|khz|mhz|gb|mb|kb|b|s|ms|us)(?!\w)', re.I)
NUMBER_UNIT = re.compile(r'(?<!\w)[+\-−]?(?:\d+(?:[.٫,٬]\d+)*|[.٫]\d+)(?:[eE][+\-]?\d+)?\s*([A-Za-zµμΩ]+)')
# These characters may express technical meaning; never erase them as punctuation.
MEANINGFUL_PUNCT = set('/\\-+±%٪=<>^*#@&_()[]{}')
TYPOGRAPHY = {'−': '-', '－': '-', '＋': '+', '‐': '-', '‑': '-'}
TIMING = re.compile(r'^\s*(?:\d{2,}:)?\d{2}:\d{2}[,.]\d{3}\s*-->\s*(?:\d{2,}:)?\d{2}:\d{2}[,.]\d{3}(?P<tail>.*)$')
SPEAKER = re.compile(r'\[Speaker\s+\d+\]', re.I)
EVENTS = re.compile(r'\[(?:يسعل|يتنفس بعمق|coughs|coughing|breathing deeply)\]', re.I)
VTT_TAGS = re.compile(r'</?(?:v|c|lang|b|i|u|ruby|rt)(?:[ .][^>]*)?>|<(?:\d{2,}:)?\d{2}:\d{2}\.\d{3}>', re.I)


def validate_text(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError('Transcript must be a string.')
    if any(ud.category(c) == 'Cs' or (ud.category(c) == 'Cc' and not c.isspace()) for c in text):
        raise ValueError('Transcript contains an invalid surrogate or non-text control character. Check its encoding.')
    return text


def validate_profile(profile=None) -> dict:
    if profile is not None and not isinstance(profile, dict):
        raise ValueError('The normalization profile must be an object.')
    p = dict(DEFAULT_PROFILE)
    if profile:
        if set(profile) - set(p):
            raise ValueError('Unknown normalization setting.')
        p.update(profile)
    if not isinstance(p['language'], str) or p['language'] not in ('ar', 'en', 'mixed'):
        raise ValueError('Language must be ar, en or mixed.')
    if any(not isinstance(p[k], bool) for k in p if k != 'language'):
        raise ValueError('Normalization switches must be booleans.')
    return p


def _nfc_items(items: list, change) -> list:
    """Compose base/mark clusters and Hangul while retaining source coverage."""
    output, cluster = [], []
    def flush():
        if not cluster:
            return
        source = ''.join(c for c, _, _ in cluster)
        value = ud.normalize('NFC', source)
        change('Unicode NFC', source, value)
        start, end = min(x[1] for x in cluster), max(x[2] for x in cluster)
        output.extend((c, start, end) for c in value)
        cluster.clear()
    for item in items:
        c = item[0]
        # Most composition is base+mark. Hangul L/V/T composition uses ccc=0.
        hangul = cluster and (0x1160 <= ord(c) <= 0x11FF or 0xD7B0 <= ord(c) <= 0xD7FF)
        if cluster and not ud.category(c).startswith('M') and not hangul:
            flush()
        cluster.append(item)
    flush()
    return output


def normalize_text(text: str, profile=None, *, baseline=False) -> dict:
    """Return scored text, raw-character spans and an explicit transformation log."""
    text = validate_text(text)
    p = validate_profile(profile)
    changes = {}
    def change(name, before, after):
        if before == after:
            return
        entry = changes.setdefault(name, {'count': 0, 'examples': []})
        entry['count'] += 1
        example = {'from': before, 'to': after}
        if example not in entry['examples'] and len(entry['examples']) < 4:
            entry['examples'].append(example)

    items = []
    for i, c in enumerate(text):
        value = c
        if c in DISPLAY_CONTROLS:
            value = ''; change('Display controls', c, value)
        elif c == '\u200b':
            value = ' '; change('Zero-width word boundary', c, value)
        elif c.isspace():
            value = ' '
        elif not baseline and p['fullwidth'] and 0xff01 <= ord(c) <= 0xff5e:
            value = ud.normalize('NFKC', c)
            change('Fullwidth ASCII typography', c, value)
        elif not baseline and p['language'] != 'en' and ud.decomposition(c).startswith(('<isolated>', '<final>', '<initial>', '<medial>')):
            # Selective Arabic presentation folding, not global NFKC:
            # ², µ, ½ and other compatibility symbols retain their identities.
            value = ud.normalize('NFKC', c)
            change('Arabic presentation forms', c, value)
        items.extend((v, i, i + 1) for v in value)
    if not baseline:
        items = _nfc_items(items, change)
        if p['language'] != 'en' and p['arabic_joiners']:
            items = fold_arabic_joiners(items, change)
    work = ''.join(c for c, _, _ in items)
    scored_items = []
    cluster_base = ''
    for index, (c, start, end) in enumerate(items):
        value = c
        if not ud.category(c).startswith('M'):
            cluster_base = c
        prev = work[index-1] if index else ''
        nxt = work[index+1] if index+1 < len(work) else ''
        if not baseline:
            if p['language'] != 'en':
                if p['diacritics'] and is_arabic_vowel(c):
                    value = ''; change('Arabic diacritics', c, value)
                # Repeated decomposed hamza marks must not recreate an alif
                # variant after it has been folded (N(N(x)) must equal N(x)).
                if p['alif'] and cluster_base in 'اأإآٱٲٳٵ' and c in '\u0653\u0654\u0655\u065f':
                    change('Alif combining signs', value, ''); value = ''
                if p['tatweel'] and value == 'ـ':
                    change('Tatweel', value, ''); value = ''
                if p['alif']:
                    folded = value.translate(ALIF); change('Alif forms', value, folded); value = folded
                value = fold_character(value, p, change)
            if p['digits']:
                folded = value.translate(DIGITS)
                if c == '٫': folded = '.'
                if c == '٬': folded = ','
                if c == '٪': folded = '%'
                change('Digit/separator shapes', value, folded); value = folded
        scored_items.extend((' ' if v.isspace() else v, start, end) for v in value)
    if not baseline:
        scored_items = _nfc_items(scored_items, change)
        work = ''.join(c for c, _, _ in scored_items)
        punctuated = []
        for index, (c, start, end) in enumerate(scored_items):
            value = c
            prev = work[index-1] if index else ''
            nxt = work[index+1] if index+1 < len(work) else ''
            if p['punctuation'] and value:
                folded = TYPOGRAPHY.get(value, value)
                # Curly apostrophes are equivalent only *inside* a word.
                if value in "’‘ʼ" and prev.isalnum() and nxt.isalnum():
                    folded = "'"
                if value in '–—' and (prev.isdigit() or nxt.isdigit()):
                    folded = '-'
                change('Punctuation typography', value, folded); value = folded
                if ud.category(value[0]).startswith('P'):
                    numeric = (value in '.,' and nxt.isdigit()) or (value == ':' and prev.isdigit() and nxt.isdigit())
                    embedded_dot = value == '.' and prev.isalnum() and nxt.isalnum()
                    apostrophe = value == "'" and prev.isalnum() and nxt.isalnum()
                    if value not in MEANINGFUL_PUNCT and not numeric and not embedded_dot and not apostrophe:
                        change('Sentence punctuation', value, ' '); value = ' '
            punctuated.extend((v, start, end) for v in value)
        scored_items = punctuated
    collapsed = []
    for c, start, end in scored_items:
        if c == ' ' and (not collapsed or collapsed[-1][0] == ' '):
            if collapsed:
                old = collapsed[-1]; collapsed[-1] = (' ', old[1], end)
            continue
        collapsed.append((c, start, end))
    if collapsed and collapsed[-1][0] == ' ':
        collapsed.pop()
    # Case handling happens last: earlier folds can create new token boundaries
    # or join a number to its unit. Protect units in the FINAL scoring context.
    if not baseline and p['lowercase']:
        work = ''.join(c for c, _, _ in collapsed)
        protected = set()
        if p['preserve_units']:
            for match in PROTECTED.finditer(work):
                protected.update(range(match.start(), match.end()))
            for match in NUMBER_UNIT.finditer(work):
                protected.update(range(match.start(), match.end()))
        lowered = []
        for index, (c, start, end) in enumerate(collapsed):
            value = c if index in protected else c.lower()
            change('Letter case', c, value)
            lowered.extend((v, start, end) for v in value)
        collapsed = _nfc_items(lowered, change)
    if not baseline and p['language'] != 'en':
        collapsed = apply_reviewed_variants(collapsed, p, change)
        collapsed = apply_suffix_rules(collapsed, p, change)
    scored = ''.join(x[0] for x in collapsed)
    if ' '.join(text.split()) != text:
        change('Whitespace', text, ' '.join(text.split()))
    return {'text': scored, 'spans': [[s, e] for _, s, e in collapsed], 'changes': changes}


def text_warnings(text: str) -> list[str]:
    """Review notices are not scores and never auto-correct the transcript."""
    warnings = []
    if any(TIMING.match(line) for line in text.splitlines()):
        warnings.append('Timestamp lines detected in scored text. Use explicit subtitle import; plain mode intentionally retains them.')
    if '\ufffd' in text:
        warnings.append('Unicode replacement character detected. Verify the original text encoding before trusting this comparison.')
    if re.search(r'<[/A-Za-z][^>]*>', text):
        warnings.append('Markup-like text detected. Plain mode does not assume it is safe to delete.')
    if re.search('[\u3400-\u9fff\u3040-\u30ff\u0e00-\u0e7f]', text):
        warnings.append('Script without reliable whitespace word boundaries detected. CER is literal; meaningful WER requires an explicit language tokenizer not included here.')
    return warnings


def extract_spoken_text(text: str, mode='plain') -> tuple[str, dict]:
    """Parse SRT/WebVTT structure only on opt-in; never drop spoken numeric lines."""
    text = validate_text(text)
    if mode == 'plain':
        return text, {'format': 'plain', 'removed': 0}
    if mode != 'subtitles':
        raise ValueError('Import format must be plain or subtitles.')
    source = text.lstrip('\ufeff').splitlines()
    if not any(TIMING.match(line) for line in source):
        return text, {'format': 'subtitles', 'removed': 0,
                      'warning': 'No valid subtitle timing lines found; the supplied text was retained.'}
    vtt = bool(source and source[0].startswith('WEBVTT'))
    lines, removed, in_cue, skip_block = [], 0, False, False
    for i, line in enumerate(source):
        stripped = line.strip()
        if not stripped:
            in_cue = skip_block = False
            continue
        if skip_block:
            removed += 1; continue
        if vtt and not in_cue and (i == 0 or re.match(r'^(NOTE(?:\s|$)|STYLE$|REGION$)', stripped)):
            removed += 1
            skip_block = i != 0
            continue
        timing = TIMING.match(line)
        if timing:
            removed += 1; in_cue = True
            line = re.sub(r'\b(?:vertical|line|position|size|align|region):\S+', '', timing['tail'])
        elif not in_cue and i + 1 < len(source) and TIMING.match(source[i+1]):
            # A cue identifier is structural only before a timing line.
            removed += 1; continue
        updated = SPEAKER.sub('', line)
        updated = EVENTS.sub('', updated)
        if vtt:
            updated = html.unescape(VTT_TAGS.sub('', updated))
        removed += int(updated != line)
        if updated.strip():
            lines.append(updated.strip())
    return '\n'.join(lines), {'format': 'subtitles', 'removed': removed,
                             'policy': 'SRT/WebVTT cue-aware; numeric payload retained; known event tags removed; no spelling correction.'}
