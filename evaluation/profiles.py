"""One fixed cleaning policy and two UI modes.

Legacy named presets remain callable to read/test earlier results. The public
interface exposes only Cleaning and No cleaning; original saved runs are not
rewritten. New evaluations compute the two views once for instant switching.
"""
from .normalizer import DEFAULT_PROFILE, validate_profile, NORMALIZER_VERSION

GENERAL = {**DEFAULT_PROFILE, 'hamza_seats': True, 'standalone_hamza': True, 'ta_marbuta': True,
           'alif_maqsura': True, 'arabic_keyboard': True, 'arabic_joiners': True,
           'fullwidth': True, 'lowercase': True, 'preserve_units': False}
CUSTOM = {**GENERAL, 'standalone_hamza': True, 'final_ta': True, 'feminine_ti': True}
CLEANING = {**CUSTOM, 'final_ya': True, 'arabic_question_forms': True}

PRESETS = {
    'conservative': dict(DEFAULT_PROFILE),
    'general': GENERAL,
    'custom': CUSTOM,
}
LABELS = {'conservative': 'Conservative', 'general': 'General orthographic',
          'custom': 'Custom Arabic tolerance'}

def profile_catalog() -> dict:
    """Public UI contract: two display modes and one backend-owned ruleset."""
    return {'version': NORMALIZER_VERSION, 'ui_version': '1.4.0',
            'default': 'cleaning', 'cleaning_profile': dict(CLEANING),
            'modes': {'normalized': 'Cleaning', 'raw': 'No cleaning'}}


def get_cleaning_profile(language='mixed') -> dict:
    """All agreed rules; apply independently to reference and hypothesis."""
    return validate_profile({**CLEANING, 'language': language})


def validate_score_view(value='normalized') -> str:
    if value not in ('normalized', 'raw'):
        raise ValueError('Choose Cleaning or No cleaning.')
    return value


def get_preset(name: str, language='mixed') -> dict:
    if name not in PRESETS:
        raise ValueError('Unknown scoring preset.')
    return validate_profile({**PRESETS[name], 'language': language})


def describe_profile(profile: dict) -> str:
    p = validate_profile(profile)
    if all(p[k] == v for k, v in CLEANING.items() if k != 'language'):
        return 'Cleaning'
    for key, value in PRESETS.items():
        if all(p[k] == v for k, v in value.items() if k != 'language'):
            return LABELS[key]
    return 'Custom rules'
