"""Word error rate for explicit microphone tests; this is not ASR confidence."""
import re
import unicodedata


def words(text):
    return re.findall(r'\w+', unicodedata.normalize('NFC', text).casefold())


def word_errors(expected, heard):
    reference, hypothesis = words(expected), words(heard)
    previous = list(range(len(hypothesis) + 1))
    for i, left in enumerate(reference, 1):
        current = [i]
        for j, right in enumerate(hypothesis, 1):
            current.append(min(previous[j] + 1, current[j-1] + 1,
                               previous[j-1] + (left != right)))
        previous = current
    count = previous[-1]
    return {'errors': count, 'reference_words': len(reference),
            'wer_percent': round(100 * count / max(1, len(reference)), 2)}
