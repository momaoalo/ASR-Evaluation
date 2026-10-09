"""General character/suffix policies, independent of a word list or the other text.

All transformations keep offsets into the original text. Aggressive suffix rules
are explicit evaluation choices, NOT assertions of grammatical equivalence.
See docs/RULE_BASED_NORMALIZATION.md for collisions, scope and source links.
"""
import unicodedata as ud

RULE_ENGINE_VERSION = '1.3.0'
# Existing profile fields remain valid. New rules are opt-in in saved/API profiles.
RULE_DEFAULTS = {
    'hamza_seats': False, 'standalone_hamza': False,
    'ta_marbuta': False, 'final_ta': False, 'alif_maqsura': False,
    'feminine_ti': False, 'final_ya': False,
    'arabic_keyboard': False, 'arabic_joiners': False,
    'fullwidth': False, 'preserve_units': True,
}
def _word_spans(text: str):
    """Word spans including combining marks, excluding every punctuation mark.

    Keep mixed alphanumeric identifiers together; suffix rules later reject them.
    Python's word-character regex does not include every combining mark, so classify explicitly.
    """
    start = None
    for i, char in enumerate(text):
        is_word = char.isalnum() or char == '_' or ud.category(char).startswith('M') or char in ('\u200c', '\u200d')
        if is_word and start is None:
            start = i
        elif not is_word and start is not None:
            yield start, i
            start = None
    if start is not None:
        yield start, len(text)


CARRIER_FOLDS = {'ؤ': 'و', 'ئ': 'ي', 'ٶ': 'و', 'ٸ': 'ي'}
KEYBOARD_FOLDS = {'ک': 'ك', 'ی': 'ي', 'ہ': 'ه'}
HAMZA_MARKS = {'\u0654', '\u0655', '\u065f'}


def is_arabic_letter(char: str) -> bool:
    return ud.category(char).startswith('L') and ud.name(char, '').startswith('ARABIC ')


def is_arabic_vowel(char: str) -> bool:
    """Arabic combining marks, but not letters or structural hamza/madda signs."""
    name = ud.name(char, '')
    return (ud.category(char).startswith('M') and name.startswith('ARABIC ')
            and 'HAMZA' not in name and 'MADDA' not in name)


def fold_character(char: str, profile: dict, change) -> str:
    """Fold a supported Arabic character anywhere in a word, keeping its base."""
    value = char
    if profile['arabic_keyboard']:
        folded = KEYBOARD_FOLDS.get(value, value)
        change('Arabic keyboard variants', value, folded); value = folded
    if profile['hamza_seats']:
        folded = CARRIER_FOLDS.get(value, value)
        if value in HAMZA_MARKS:
            folded = ''
        change('Hamza carrier folding', value, folded); value = folded
    if profile['standalone_hamza'] and value in ('ء', 'ٴ'):
        change('Standalone hamza omission (custom)', value, ''); value = ''
    if profile['alif_maqsura'] and value == 'ى':
        change('Alif maqsura / yeh', value, 'ي'); value = 'ي'
    return value


def fold_arabic_joiners(items: list, change) -> list:
    """Remove Arabic-internal joining controls only; never remove spaces."""
    # Nearest non-mark/control neighbors, computed once to avoid quadratic
    # scans on a long sequence of ZWJ/ZWNJ characters.
    ignored = lambda c: ud.category(c).startswith('M') or c in ('\u200c', '\u200d')
    left, right = [], [False] * len(items)
    previous = False
    for char, _, _ in items:
        left.append(previous)
        if not ignored(char):
            previous = is_arabic_letter(char)
    following = False
    for i in range(len(items)-1, -1, -1):
        char = items[i][0]; right[i] = following
        if not ignored(char):
            following = is_arabic_letter(char)
    output = []
    for i, item in enumerate(items):
        char, start, end = item
        if char in ('\u200c', '\u200d') and left[i] and right[i]:
            change('Arabic internal joiner', char, '')
            if output:
                previous = output[-1]; output[-1] = (previous[0], previous[1], end)
            continue
        output.append(item)
    return output


def apply_suffix_rules(items: list, profile: dict, change) -> list:
    """Rule-based final-letter folds on all Arabic words, including unseen ones.

    - ta_marbuta: terminal ة -> ه (not ت); no lexical dictionary.
    - final_ta: terminal ة/ه/ت -> ه; deliberately loses grammatical information.
    - feminine_ti: terminal تي+ -> ت if >=3 preceding/base letters remain.
    - final_ya: terminal ي/ى run omitted if >=3 letters remain. This is NOT a
      morphological detector; 'كتابي' and 'كتاب' can then compare equal.
    Suffix deletion happens before final-ta folding for a stable canonical form.
    """
    if not any(profile[k] for k in ('ta_marbuta', 'final_ta', 'feminine_ti', 'final_ya')):
        return items
    text = ''.join(c for c, _, _ in items)
    output, cursor = [], 0
    for start, end in _word_spans(text):
        output.extend(items[cursor:start])
        token = list(items[start:end])
        bases = [i for i, (c, _, _) in enumerate(token) if not ud.category(c).startswith('M')]
        if not bases or not all(is_arabic_letter(token[i][0]) for i in bases):
            output.extend(token); cursor = end; continue
        word = ''.join(token[i][0] for i in bases)
        remaining = len(bases)
        if profile['final_ya']:
            while remaining > 0 and word[remaining-1] in ('ي', 'ى'):
                remaining -= 1
            if remaining < 3:
                remaining = len(bases)
            label = 'Final yeh omission (custom)'
        elif profile['feminine_ti']:
            while remaining > 0 and word[remaining-1] == 'ي':
                remaining -= 1
            if remaining < 3 or word[remaining-1] != 'ت':
                remaining = len(bases)
            label = 'Terminal ti / t equivalence (custom)'
        if remaining < len(bases):
            cut = bases[remaining]
            removed_end = token[-1][2]
            before = ''.join(c for c, _, _ in token)
            token = token[:cut]
            last = token[-1]; token[-1] = (last[0], last[1], removed_end)
            change(label, before, ''.join(c for c, _, _ in token))
            bases = bases[:remaining]
        last_base = bases[-1]
        char, begin, finish = token[last_base]
        if (profile['ta_marbuta'] and char == 'ة') or (profile['final_ta'] and char in ('ة', 'ت')):
            before = ''.join(c for c, _, _ in token)
            token[last_base] = ('ه', begin, finish)
            name = 'Final ta/heh equivalence (custom)' if profile['final_ta'] else 'Final teh marbuta / heh'
            change(name, before, ''.join(c for c, _, _ in token))
        output.extend(token)
        cursor = end
    output.extend(items[cursor:])
    return output


def policy_warnings(profile: dict) -> list[str]:
    notes = []
    if profile['language'] != 'en':
        if profile['hamza_seats'] or profile['alif']:
            notes.append('Hamza/alif folding is orthographic tolerance, not semantic verification.')
        if profile['ta_marbuta']:
            notes.append('Final ة/ه folding is general, not dictionary-based; e.g. كرة/كره can collapse.')
        if profile['final_ta']:
            notes.append('CUSTOM: final ة/ه/ت are equal; genuine differences such as قوة/قوت can disappear.')
        if profile['feminine_ti']:
            notes.append('CUSTOM: terminal تي/ت is a spelling heuristic, not a feminine-suffix detector; بيتي/بيت can collapse.')
        if profile['final_ya']:
            notes.append('CUSTOM: final ي/ى is omitted where at least three letters remain; كتابي/كتاب can collapse.')
        if profile['standalone_hamza']:
            notes.append('Standalone hamza omission can erase a real consonant; see the raw and conservative scores.')
        if profile['alif_maqsura']:
            notes.append('ى/ي folding may also merge meaningful words such as على/علي.')
    if profile['lowercase'] and not profile['preserve_units']:
        notes.append('Global lowercase also folds case-sensitive units/identifiers; use the protected-units option for technical text.')
    return notes
