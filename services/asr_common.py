"""Shared result contract and safe provider errors. No credentials enter results."""
from storage import now

class ProviderError(Exception):
    def __init__(self, message, code='provider_error'):
        super().__init__(message)
        self.code = code


def classify_api_error(status: int) -> ProviderError:
    messages = {
        401: 'Authentication failed. Replace the provider API key in Connections.',
        403: 'The provider denied access. Check key permissions and account entitlement.',
        413: 'The provider rejected the file size.',
        422: 'The provider rejected the audio or request settings.',
        429: 'Provider rate limit or quota reached. Retry explicitly after checking your account.',
    }
    return ProviderError(messages.get(status, f'Provider returned HTTP {status}. No automatic duplicate submission was made.'), 'http_' + str(status))


def build_model_result(key: str, label: str, text: str, *, settings: dict,
                       elapsed_ms=None, provenance='live', raw_text=None, metadata=None) -> dict:
    if not isinstance(text, str):
        raise ProviderError('Provider response did not contain a text string.', 'response_schema')
    return {'key': key, 'label': label, 'status': 'success', 'speech_text': text,
            'raw_text': text if raw_text is None else raw_text, 'request_settings': settings,
            'elapsed_ms': elapsed_ms, 'received_at': now(), 'provenance': provenance,
            'metadata': metadata or {}, 'cache_hit': False}
