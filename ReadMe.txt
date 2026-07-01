

Data Journey:

Frontend GUI
Purpose: User records and edits text in frontend GUI. User submits query to LLM. Only text data and user name are passed to backend.
->
"BACKEND" API
Purpose: Data flows to the "backend" (In quotes cause not really hosted on anything). This is where the data enters the Data Pipeline and will soon be processed and given attribution results, a confidence score and eventually a label. Holds the business logic too.
->
Rate Limiter
Purpose: Checks if the user is spamming the endpoint before forwarding to classifier signals, etc. Will quickly shut down spam requests
->
Signal 1
Purpose: Undecided now but will most likely be a heurisitc signal. Checking physical charactersitics of text. Will return a attribution result.
->
Signal 2
Purpose: Undecided for now but will most likely be a LLM filter making sure the content of the message is appropriate.
->
Confidence Scoring Algo
Purpose: takes the attribution results from signals 1 and 2 and uses them to give a confidence score. Returns the transparency label to the API.
-> 
"Backend" API
Purpose: Takes all the info collected and sends it back neatly in a JSON response to give to the user.
-> 


Signal 1: Stylometric Heuristics
Properties: Measures sentence length variance, type-token ratio (vocabulary diversity), punctuation density, or average sentence complexity. AI text tends to be more uniform; human writing is more variable.
Blind-Spot: This signal measures the heurisitcs that the text shows but not the words themselves. AI tends to use the same words/phrases a lot and talks with a consistent tone that this signal will not be able to measure

Signal 2:
LLM-based classification (Groq):
Properties: asks the Groq model to assess whether text reads as human or AI-generated. Captures semantic and stylistic coherence holistically.
Blind-spot: Does not measure the heuristics of the text. AI tends to be more uniform while human writing is more variable this only measures the meaning behind the words being used.

False-Positives: What happens when AI misclassifies a human writers work? I will fine-tune the confidence scores so this will happen less. I want to make sure the confidence score is very certain a user's text is AI before ruling it as AI (Only a high confidence score can result in AI work). If the users' work is falsely flagged as being AI I will have an appeals proccess, which will appear in the user GUI. That captures the user's reasoning as to why their writing is not AI, log the Appeal and write it to the log system along with the AI's original response.


API's:

Rate limiter: Limits the rate at which users are able to send requests. Accepts the user_nm, time and will use IP as well. I will use flask limiter to handle rate limiting

Attribution Analysis API(text): Scores a given piece of text based on how likely it's AI ( Signals, Confidence Scoring). Gives back a json object of the Confidence scoring and respective tag.

Appeals API (user_nm, user reasoning, Confidence score/Tag, Reuqest Number): Reclassifies a users' request as Under Review and logs the appeal.

Detection Signals:

    Signal 1: Stylometric Heuristics
    Properties: Measures sentence length variance, type-token ratio (vocabulary diversity), punctuation density, or average sentence complexity. AI text tends to be more uniform; human writing is more variable.
    Output: A normalized attribution result between 0 and 1 (0 = human and 1 = AI)

    Signal 2:
    LLM-based classification (Groq):
    Properties: asks the Groq model to assess whether text reads as human or AI-generated. Captures semantic and stylistic coherence holistically.
    Output: A normalized attribution result between 0 and 1 (0 = human and 1 = AI). Prompt AI to come up with one.

    Signal Combination: I will use a weighted  weighted average to combine the two scores into one final attribution score between 0 and 1, this makes the most sense to combine the best parts of both signals in a combined manner

Uncertainty Representation:
    I will lean towards human writing for all submitted texts, so unless the confidence score is very high I will classify as Human. I will map direclty from confidence score to label using pre-structured intervals. For thresholds. Likely Huma (0 to .45), uncertain (0.45 to 0.70) and Likely AI from (0.70 to 1)

Transparency Label Design:
    Labels:

    Likely Human :  0 - 0.45
    Inconclusive : 0.45 - 0.70
    Likely AI : 0.7 - 1


Confidence Score Examples:

cd "c:/Users/mtemk/CodePath Ai201/ai201-project4-provenance-guard" && curl -s -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"creator_id":"me","text":"ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won'\''t go back unless someone drags me there"}' | python -m json.tool
{
    "confidence": 0.127,
    "content_id": "d2afbe0ea8c84228adf59de937a58ddd",
    "label": "Likely Human",
    "reason": "The text features an idiosyncratic voice and specific lived details, indicating a high likelihood of human authorship.",
    "signals": {
        "signal1": 0.054,
        "signal2": 0.2
    }
}

 cd "c:/Users/mtemk/CodePath Ai201/ai201-project4-provenance-guard" && curl -s -X POST http://localhost:5000/submit   -H "Content-Type: application/json"   -d '{"creator_id":"me","text":"Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment."}' | python -m json.tool
{
    "confidence": 0.775,
    "content_id": "9b8c11a14a80408b87ce51db43d8e720",
    "label": "Likely AI",
    "reason": "The text features a suspiciously uniform tone and generic phrasing.",
    "signals": {
        "signal1": 0.749,
        "signal2": 0.8
    }
}

Appeals Workflow:

    Only people marked as uncertain or Likely AI can submit an appeal. The user needs to provide a reasoning about why their text might be marked as AI. The system also collects their user_nm, text_id, label, confidence score. Once an appeal is recieved, the status of their text is marked as Under Review and the appeal gets logged along with the systems orginal response.
    If a human looks at the appeal queue, they should have the post in question, the system's log that marked the text as suspicious, the users' appeal message and the users' past history if needed

Anticipated Edge Cases: 
    I suspect my system might handle annotated texts and AI paraphrasing might act poorly, especially if the user partially uses AI in their response. This is also something that the system design does not account for. Writing that mimics AI like certains types of repetitve prose or a robotic tone might also trigger an AI label.


If I were deploying this project for real. I would make sure to properly host the server on an external machine make my enpoints more secure against attackers by requiring more authorization

Known Limitations:
This system is not very good at shorter version of text. For example, comments or AI paraphrased work will be the most likely to get flagged incoorectly. Short pieces of text are weak to heurisitc analysis due to the lack of variance in sentence structure. AI Paraphrasing will not be good either because it contains AI work which this system detects for and will maintain many of the same sentence structures.

Spec Reflection:
The spec helped me by getting to identify my endpoints and how they work with each other before I created them. This gave me a really good view of the scope of the project. One way my implementation diverged from my spec was that i didn't need a frontend GUI to impolement this whole system. It may be easier in the future to test this system if i include one, but it would take a lot of time to implement


Loom Video Link:https://www.loom.com/share/3653987cd88d4508b2eec73f7c4a4525
