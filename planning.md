Design Descions:



Detection Signals:

    Signal 1: Stylometric Heuristics
    Properties: Measures sentence length variance, type-token ratio (vocabulary diversity), punctuation density, or average sentence complexity. AI text tends to be more uniform; human writing is more variable.
    Output: A normalized attribution result between 0 and 1 (0 = human and 1 = AI)

    Signal 2:
    LLM-based classification (Groq):
    Properties: asks the Groq model to assess whether text reads as human or AI-generated. Captures semantic and stylistic coherence holistically.
    Output: A normalized attribution result between 0 and 1 (0 = human and 1 = AI). Prompt AI to come up with one.

    Signal Combination: I will use a weighted  weighted average to combine the two scores into one final attribution score between 0 and 1

Uncertainty Representation:
    I will lean towards human writing for all submitted texts, so unless the confidence score is very high I will classify as Human. I will map direclty from confidence score to label using pre-structured intervals. For thresholds. Likely Huma (0 to .45), uncertain (0.45 to 0.70) and Likely AI from (0.70 to 1)

Transparency Label Design:
    Labels:

    Likely Human :  0 - 0.45
    Inconclusive : 0.45 - 0.70
    Likely AI : 0.7 - 1


Appeals Workflow:

    Only people marked as uncertain or Likely AI can submit an appeal. The user needs to provide a reasoning about why their text might be marked as AI. The system also collects their user_nm, text_id, label, confidence score. Once an appeal is recieved, the status of their text is marked as Under Review and the appeal gets logged along with the systems orginal response.
    If a human looks at the appeal queue, they should have the post in question, the system's log that marked the text as suspicious, the users' appeal message and the users' past history if needed

Anticipated Edge Cases: 
    I suspect my system might handle annotated texts and AI paraphrasing might act poorly, especially if the user partially uses AI in their response. This is also something that the system design does not account for. Writing that mimics AI like certains types of repetitve prose or a robotic tone might also trigger an AI label.

## Architecture

                          PROVENANCE GUARD — SYSTEM DESIGN FLOW
═══════════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND GUI                                                                          │
│  • User writes / edits text                                                           │
│  • Submits { username, text }                                                         │
│  • Renders result label + confidence  •  Shows "Retry-After" on 429                   │
│  • Hosts the Appeals form                                                             │
└───────────────────────────────────┬─────────────────────────────────────────────────┘
                                     │  HTTP POST /analyze   { username, text }
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  BACKEND API  (Flask)                                                                  │
│                                                                                       │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │  RATE LIMITER  (flask-limiter — runs FIRST, before any work)                  │   │
│   │  key = "username:ip"      limits = 5/min (burst) , 100/day (cost cap)         │   │
│   │                                                                              │   │
│   │      OVER LIMIT ──────────────► 429 + Retry-After ──────────► back to GUI    │   │
│   │      UNDER LIMIT ▼                                                            │   │
│   └──────────────────┼──────────────────────────────────────────────────────────┘   │
│                      │                                                                │
│        ┌─── input guard: word_count < 75 ? ──► flag "short text" (cap at Inconclusive)│
│        ▼                                                                              │
│   ┌──────────────────────────┐        ┌──────────────────────────────────────────┐  │
│   │  SIGNAL 1                 │        │  SIGNAL 2                                  │  │
│   │  Stylometric heuristics   │        │  LLM judgment (Groq)                       │  │
│   │  textstat + nltk          │        │  prompt → semantic / tone assessment       │  │
│   │  • sentence-len variance  │        │  • returns label + confidence + reason     │  │
│   │  • type-token ratio       │        │                                            │  │
│   │  • punctuation density    │        │  blind spot: ignores statistical shape     │  │
│   │  • readability spread     │        │                                            │  │
│   │  blind spot: ignores      │        │                                            │  │
│   │    meaning                │        │                                            │  │
│   │  ► score A (0–1)          │        │  ► score B (0–1)  + reason text            │  │
│   └────────────┬─────────────┘        └─────────────────────┬────────────────────┘  │
│                │                                             │                        │
│                └──────────────────┬──────────────────────────┘                        │
│                                   ▼                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │  CONFIDENCE SCORING ALGO                                                       │   │
│   │  • fuse A + B  (weighted average)  ► combined score                           │   │
│   │  • guardrails:                                                                │   │
│   │       |A − B| > 0.5      → force Inconclusive  (signals disagree)             │   │
│   │       word_count < 75    → cap at Inconclusive                                │   │
│   │  • map score → LABEL  (asymmetric, AI is hard to reach):                      │   │
│   │       ≤ 0.35  → "Likely human-written"                                        │   │
│   │       0.35–0.80 → "Inconclusive"                                              │   │
│   │       ≥ 0.80  → "Likely AI-generated"                                         │   │
│   └────────────────────────────────────┬────────────────────────────────────────┘   │
│                                         │                                            │
│              ┌──────────────────────────┴───────────────┐                            │
│              ▼                                           ▼                            │
│   ┌────────────────────────┐               ┌──────────────────────────────┐         │
│   │  RESPONSE BUILDER       │               │  LOG SYSTEM                   │         │
│   │  JSON: { label,         │               │  store: text, scores A/B,     │         │
│   │   confidence, signals,  │──────────────►│  label, Groq reason, ts,      │         │
│   │   reason }              │               │  username                     │         │
│   └───────────┬─────────────┘               └──────────────┬───────────────┘         │
│               │                                            ▲                          │
└───────────────┼────────────────────────────────────────────┼─────────────────────────┘
                │  200 + JSON                                  │  appeal record
                ▼                                              │  (links to original verdict)
┌─────────────────────────────────────────────────────────────┴─────────────────────────┐
│  FRONTEND GUI                                                                          │
│  • Shows label + confidence                                                           │
│  • If "Likely AI-generated" → offer APPEAL  ──► POST /appeal { reason } ──► LOG SYSTEM │
└───────────────────────────────────────────────────────────────────────────────────────┘

Submission Flow: Frontend GUI send to the Rate limiter, if api call isn't limited, then sent to confidence record. Confidence record then sends data to both Heuristic and LLM signalas and gets a response from both, that response if turned into a confidence score and a label from there. Then, sent back as a JSON object.

Appeals flow: Frontend GUI sends to rate limited, if api call isn't limited, then sent to appeals API. The appeals flow then logs the appeal for the given user/text combo and sends back an "under review label" to the frontend GUI.

##AI Tool Plan
Standard AI stuff

M3 (submission endpoint + first signal): I will use Claude to help me build the first heuristics signal. I will ask it to build it according to the specs I am creating now. i will then verify it works with several examples and fine tune the model so it is more accurate.

M4 (second signal + confidence scoring): I will use Claude to help me create an interface to interact with the GROQ LLm using my API key. I will review the code and the prompt it sends to groq

M5 (Production Layer): I will use Calude to help assist me with creating the Production layer including the Rate Limiter and appeals endpoint. I will then verify the code according to the specs in my planning.md




   