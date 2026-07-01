"""
Signal 1 — Stylometric Heuristics
=================================
Estimates how "AI-like" a piece of text is using only statistical/stylistic
features (no ML model downloads). Returns a normalized score in [0, 1] where
0 = clearly human and 1 = clearly AI.

Idea: AI text tends to be UNIFORM (low sentence-length variance, flat
readability, "safe" mid-range vocabulary). Human writing is more VARIABLE.
We measure a few features, map each to a 0-1 "AI-ness" contribution, then
average them.

Dependencies: textstat, nltk
One-time setup (run once, e.g. at app startup):
    import nltk
    nltk.download('punkt')
    nltk.download('punkt_tab')   # required on newer nltk versions
"""

import statistics

import nltk
import textstat

# ---------------------------------------------------------------------------
# Tunable anchors.  Each pair says "what value looks human" vs "what value
# looks AI" for a feature.  These are first-guess values — tune them against
# real sample texts.  squash() maps a raw measurement onto 0..1 between them.
# ---------------------------------------------------------------------------
VARIANCE_HUMAN = 48.0   # high sentence-length variance => human
VARIANCE_AI    = 15.0   # low variance => AI (uniform)

TTR_HUMAN = 0.75        # high type-token ratio (diverse vocab) => human
TTR_AI    = 0.45        # lower diversity => AI

EASE_HUMAN = 75.0       # flesch_reading_ease: easy/high => human
EASE_AI    = 10.0       # dense, low-readability => AI (tightened)

PUNCT_HUMAN = 0.12      # richer/irregular punctuation => human
PUNCT_AI    = 0.04      # sparse, regular punctuation => AI

# Per-feature weights (sum to 1.0). Calibrated on real samples: readability is
# the reliable discriminator, variance helps some, while TTR and punctuation are
# near-noise at short text lengths so they carry only token weight.
WEIGHT_EASE     = 0.60
WEIGHT_VARIANCE = 0.30
WEIGHT_TTR      = 0.05
WEIGHT_PUNCT    = 0.05

# Below this many words the features are too noisy to trust; return neutral.
MIN_WORDS_FOR_CONFIDENCE = 35
NEUTRAL_SCORE = 0.5


def _ensure_nltk_data():
    """Make sure the tokenizer data is present (download once if missing)."""
    for pkg in ("punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{pkg}")
        except LookupError:
            nltk.download(pkg)


def squash(value, human_anchor, ai_anchor):
    """
    Map a raw feature value onto a 0..1 "AI-ness" scale by its linear position
    between the human anchor (-> 0) and the AI anchor (-> 1). Clamped to [0,1].
    Works whether the AI anchor is higher or lower than the human anchor.
    """
    if human_anchor == ai_anchor:
        return NEUTRAL_SCORE
    frac = (value - human_anchor) / (ai_anchor - human_anchor)
    return max(0.0, min(1.0, frac))


def run_signal_1(text):
    """
    Compute the stylometric AI-ness score for `text`.

    Returns:
        float in [0, 1]  (0 = human, 1 = AI).
        Returns NEUTRAL_SCORE (0.5) for empty or very short text, since the
        features are unreliable there.
    """
    if not text or not text.strip():
        return NEUTRAL_SCORE

    _ensure_nltk_data()

    sentences = nltk.sent_tokenize(text)
    tokens = nltk.word_tokenize(text)
    alpha_words = [t.lower() for t in tokens if t.isalpha()]

    # Too short to judge -> stay neutral (scoring layer will cap the label).
    if len(alpha_words) < MIN_WORDS_FOR_CONFIDENCE:
        return NEUTRAL_SCORE

    # --- Feature A: sentence-length variance --------------------------------
    sent_lengths = [len(nltk.word_tokenize(s)) for s in sentences]
    length_variance = statistics.pvariance(sent_lengths) if len(sent_lengths) > 1 else 0.0
    variance_score = squash(length_variance, VARIANCE_HUMAN, VARIANCE_AI)

    # --- Feature B: type-token ratio (vocabulary diversity) -----------------
    ttr = len(set(alpha_words)) / len(alpha_words)
    ttr_score = squash(ttr, TTR_HUMAN, TTR_AI)

    # --- Feature C: readability spread (textstat) ---------------------------
    reading_ease = textstat.flesch_reading_ease(text)
    ease_score = squash(reading_ease, EASE_HUMAN, EASE_AI)

    # --- Feature D: punctuation density -------------------------------------
    punct_tokens = [t for t in tokens if not t.isalnum() and not t.isspace()]
    punct_density = len(punct_tokens) / len(tokens) if tokens else 0.0
    punct_score = squash(punct_density, PUNCT_HUMAN, PUNCT_AI)

    # --- Combine: weighted sum (readability-dominant) -----------------------
    return (
        WEIGHT_EASE * ease_score
        + WEIGHT_VARIANCE * variance_score
        + WEIGHT_TTR * ttr_score
        + WEIGHT_PUNCT * punct_score
    )


if __name__ == "__main__":
    sample = (
        "The mitochondria is the powerhouse of the cell. It produces energy. "
        "This energy is used by the cell. The process is called respiration."
    )
    print(f"Signal 1 score: {run_signal_1(sample):.3f}")
