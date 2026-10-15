******Reflection for AICC-230 Final Project*****

1.	What I built:

        o	A fully local research assistant over 29 falconry PDFs
        o	Ollama embeddings, MariaDB vector search, an MCP server with a semantic_search tool, and an agent loop running on Ollama’s qwen2.5.

2.	What worked:

        o	Strong matches had distances around 0.21 to 0.25, while unrelated questions landed around 0.46 to 0.49 (the rabbit question was 0.4907). That gap let the agent tell relevant from irrelevant.
        o	The agent searched, read the results, and answered with page citations
        o	When the documents didn’t cover a question, it declined with the exact required sentence.

3.	What broke and how I found it: 

        o	Vector index error 1071: the id column was a long text type, and the fix was CHAR(64) with an ascii collation.
        o	The model skipping the search: it declined without calling the tool, so I added a guard that nudges it to search first.
        o	Citations printing as a literal “(source, p.17)”: the prompt example had been copied word for word, so I changed it to (filename, p.N) with a real example.

4.	What surprised me about the model: 

        o	When asking about rabbi diets, it tried to look for raptor diets but was too far a score to be relevant and then told me so.
        o	A misspelled word (pemit “permit”) still found the right chunk from the question.
        o	Without the guard, declining without searching looked safe, but wasn’t evidence of grounding.

5.	Limits and what I would change: 

        o	Chunks are large (about 4000 characters), so one hit can mix topics
        o	There is no memory between questions
        o	Some my PDF state documents overlapped in information.
        o	Next steps: smaller chunks, a distance cutoff, remembering previous questions, and a simple UI would be cool.

6.	How I used AI: 

        o	I used Claude to help write, debug the code and guide me through the process, then ranevery 
            step myself and checked answers against the PDF pages.

