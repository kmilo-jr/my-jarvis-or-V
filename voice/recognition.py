"""Conservative quality checks; never turn a partial transcript into an action."""
import math


def assess_segments(segments, config):
    scores = []
    texts = []
    issues = set()
    for segment in segments:
        text = str(segment.text or '').strip()
        if not text:
            continue
        texts.append(text)
        score = getattr(segment, 'avg_logprob', None)
        silence = float(getattr(segment, 'no_speech_prob', 0) or 0)
        compression = float(getattr(segment, 'compression_ratio', 0) or 0)
        if score is not None:
            score = float(score)
            if not math.isfinite(score):
                issues.add('invalid_confidence')
            else:
                scores.append(score)
                if score < float(config.get('recognition_min_logprob', -1.35)):
                    issues.add('low_confidence')
                if silence > 0.6 and score < -1.0:
                    issues.add('no_speech')
                if compression > 2.4 and score < -0.5:
                    issues.add('repetition')
        # A bad segment could contain a negation. Reject the whole utterance.
    return {'text': ' '.join(texts), 'score': min(scores) if scores else None,
            'issues': sorted(issues)}
