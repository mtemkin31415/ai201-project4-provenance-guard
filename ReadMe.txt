

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



