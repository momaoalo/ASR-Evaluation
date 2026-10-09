"""Reviewed, opt-in spelling equivalences. No prediction-to-reference matching.

The fixed JSON dictionary is applied independently to both sides. It never
learns replacements from the current hypothesis, and never drops conjunctions.
"""
import hashlib
import json
import re
from pathlib import Path

_RULES_BYTES = Path(__file__).with_name('arabic_variants.json').read_bytes()
_RULES = json.loads(_RULES_BYTES)
VARIANTS_ID = hashlib.sha256(_RULES_BYTES).hexdigest()[:16]
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_QUESTION = re.compile(r"(?<!\w)مما(?=\s+تشكو(?!\w))")
# Enumerated prefix+word forms, not a morphological guess. Eg وجه and كتابه
# are absent and stay distinct from وجة and كتابة.
_ALIASES = {}
for _word in _RULES['canonical_words']:
    if not isinstance(_word, str) or not re.fullmatch(r'[ء-ي]+ة', _word):
        raise ValueError('Arabic spelling entries must be Arabic words ending in ة.')
    for _prefix in _RULES['prefixes']:
        if not isinstance(_prefix, str) or (_prefix and not re.fullmatch(r'[ء-ي]+', _prefix)):
            raise ValueError('Invalid Arabic spelling prefix.')
        _canonical = _prefix + _word
        _ALIASES[_canonical[:-1] + 'ه'] = _canonical


def apply_reviewed_variants(items: list, profile: dict, change) -> list:
    """Apply fixed aliases and retain raw source spans for every scored char."""
    text = ''.join(c for c, _, _ in items)
    if profile['arabic_spelling']:
        revised = list(items)
        for match in _WORD.finditer(text):
            before = match.group()
            after = _ALIASES.get(before)
            if after:
                # Equal-length spelling replacement retains each original span.
                pos = match.end() - 1
                _, start, end = revised[pos]
                revised[pos] = (after[-1], start, end)
                change('Reviewed Arabic spelling', before, after)
        items = revised
        text = ''.join(c for c, _, _ in items)
    if profile['arabic_question_forms']:
        revised, cursor = [], 0
        for match in _QUESTION.finditer(text):
            start, end = match.span()
            revised.extend(items[cursor:start])
            revised.append(items[start])
            # Last scored م also covers the removed ا for raw-word highlighting.
            revised.append(('م', items[start + 1][1], items[end - 1][2]))
            change('Question phrase equivalence', 'مما تشكو', 'مم تشكو')
            cursor = end
        revised.extend(items[cursor:])
        items = revised
    return items
