"""
Provenance Guard — Flask backend skeleton
==========================================
Exposes POST /submit. The rate limiter runs FIRST (before any signal work).
If the request is under the limit, we run Signal 1 (implemented) plus stubs for
Signal 2, score fusion, and label classification, then return a JSON verdict.

Only Signal 1 is implemented here. Signal 2, scoring, logging, and appeals are
deliberately left as TODO stubs so the skeleton runs end-to-end first.
"""

import json
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter

from signal1 import run_signal_1
from signal2 import run_signal_2

load_dotenv()  # loads GROQ_API_KEY etc. from .env

# Single append-only log file (one JSON object per line — JSON Lines).
# An appeal updates its verdict row in place (adds status + appeal reason).
LOG_FILE = os.path.join(os.path.dirname(__file__), "provenance_log.jsonl")

# Only these verdicts may be appealed (planning.md: "uncertain or Likely AI").
APPEALABLE_LABELS = {"Inconclusive", "Likely AI"}
UNDER_REVIEW = "Under Review"

# Label thresholds (from planning.md — bias toward "Likely Human").
HUMAN_MAX = 0.45          # 0.00 - 0.45  -> Likely Human
INCONCLUSIVE_MAX = 0.70   # 0.45 - 0.70  -> Inconclusive ; >= 0.70 -> Likely AI

# Guardrails applied during scoring, not inside the signals.
DISAGREEMENT_LIMIT = 0.5  # |signal1 - signal2| above this -> force Inconclusive
MIN_WORDS = 35            # below this -> cap label at Inconclusive

# Weighted-average weights for combining the two signals.
WEIGHT_SIGNAL_1 = 0.5
WEIGHT_SIGNAL_2 = 0.5


def user_ip_key():
    """Rate-limit key: 'creator_id:ip'. Falls back to IP if no creator_id given."""
    data = request.get_json(silent=True) or {}
    creator_id = data.get("creator_id", "anon")
    return f"{creator_id}:{request.remote_addr}"


app = Flask(__name__)
limiter = Limiter(
    key_func=user_ip_key,
    app=app,
    default_limits=["100 per day"],   # cost cap
    headers_enabled=True,             # send X-RateLimit-* and Retry-After
)


# ---------------------------------------------------------------------------
# STUBS — to be implemented next. Each returns a placeholder for now.
# (run_signal_1 and run_signal_2 are now real, imported above.)
# ---------------------------------------------------------------------------
def combine_scores(signal1, signal2):
    """TODO: refine. For now, weighted average of the two signal scores."""
    return WEIGHT_SIGNAL_1 * signal1 + WEIGHT_SIGNAL_2 * signal2


def classify(score, signal1, signal2, word_count):
    """
    TODO: finalize. Map combined score -> label, applying guardrails:
      - signals disagree by > DISAGREEMENT_LIMIT  -> Inconclusive
      - word_count < MIN_WORDS                    -> cap at Inconclusive
    """
    if abs(signal1 - signal2) > DISAGREEMENT_LIMIT:
        return "Inconclusive"
    if word_count < MIN_WORDS and score >= INCONCLUSIVE_MAX:
        return "Inconclusive"
    if score < HUMAN_MAX:
        return "Likely Human"
    if score < INCONCLUSIVE_MAX:
        return "Inconclusive"
    return "Likely AI"


def log_result(content_id, creator_id, text, s1, s2, score, label, reason):
    """Append one verdict to the log file as a JSON line, keyed by content_id."""
    entry = {
        "content_id": content_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "creator_id": creator_id,
        "text": text,
        "signal1": round(s1, 3),
        "signal2": round(s2, 3),
        "confidence": round(score, 3),
        "label": label,
        "reason": reason,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def get_log():
    """Return all log entries (list of dicts). Empty list if nothing logged yet."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def find_verdict(content_id):
    """Return the verdict log entry for a content_id, or None."""
    for entry in get_log():
        if entry.get("content_id") == content_id:
            return entry
    return None


def update_verdict(content_id, updates):
    """
    Apply `updates` to the log row with this content_id and rewrite the file.
    Returns the updated entry, or None if no matching row exists.
    """
    entries = get_log()
    updated = None
    for entry in entries:
        if entry.get("content_id") == content_id:
            entry.update(updates)
            updated = entry
            break
    if updated is not None:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
    return updated


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")  # burst cap; runs BEFORE the body below
def submit():
    data = request.get_json(silent=True) or {}
    creator_id = data.get("creator_id")
    text = data.get("text")

    # --- input validation ---
    if not creator_id or not isinstance(text, str) or not text.strip():
        return jsonify(error="Both 'creator_id' and non-empty 'text' are required."), 400

    word_count = len(text.split())

    # Unique id for this submission (planning.md's text_id) so an appeal or a
    # log entry can point back to this exact verdict.
    content_id = uuid.uuid4().hex

    # --- run signals ---
    s1 = run_signal_1(text)              # implemented
    s2, reason = run_signal_2(text)      # stub for now

    # --- fuse + label ---
    score = combine_scores(s1, s2)
    label = classify(score, s1, s2, word_count)

    log_result(content_id, creator_id, text, s1, s2, score, label, reason)

    return jsonify(
        content_id=content_id,
        label=label,
        confidence=round(score, 3),
        signals={"signal1": round(s1, 3), "signal2": round(s2, 3)},
        reason=reason,
    )


@app.route("/logs", methods=["GET"])
def logs():
    """Return every logged verdict."""
    return jsonify({"entries": get_log()})


@app.route("/appeal", methods=["POST"])
@limiter.limit("5 per minute")  # appeals go through the rate limiter too
def appeal():
    """
    Submit an appeal for a prior verdict.

    Body: { content_id, creator_reasoning }
    Rules (planning.md):
      - only "Inconclusive" or "Likely AI" verdicts may be appealed
      - a reasoning is required
    The creator is taken from the stored verdict (no need to resend it).
    On success: updates the verdict's row in place (status -> "Under Review",
    plus the appeal reasoning and time) and returns an "Under Review" status. The
    original verdict fields are preserved, so the record keeps the system's
    original response alongside the appeal.
    """
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    # --- input validation ---
    if not content_id or not isinstance(creator_reasoning, str) or not creator_reasoning.strip():
        return jsonify(
            error="'content_id' and a non-empty 'creator_reasoning' are required."
        ), 400

    # --- look up the original verdict (the system's "original response") ---
    verdict = find_verdict(content_id)
    if verdict is None:
        return jsonify(error=f"No verdict found for content_id '{content_id}'."), 404

    # --- only uncertain / likely-AI verdicts are appealable ---
    if verdict.get("label") not in APPEALABLE_LABELS:
        return jsonify(
            error=f"Only {sorted(APPEALABLE_LABELS)} verdicts can be appealed; "
                  f"this one is '{verdict.get('label')}'."
        ), 409

    # --- already appealed? ---
    if verdict.get("status") == UNDER_REVIEW:
        return jsonify(error="This text has already been appealed."), 409

    # --- update the verdict row in place with the appeal ---
    update_verdict(content_id, {
        "status": UNDER_REVIEW,
        "creator_reasoning": creator_reasoning.strip(),
        "appeal_timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return jsonify(
        status=UNDER_REVIEW,
        content_id=content_id,
        message="Your appeal has been received and your text is now under review.",
    )


@app.errorhandler(429)
def ratelimit_handler(e):
    """Friendly JSON for throttled requests; flask-limiter sets Retry-After."""
    return jsonify(
        error="Too many requests — please slow down.",
        detail=str(e.description),
    ), 429


if __name__ == "__main__":
    app.run(debug=True)
