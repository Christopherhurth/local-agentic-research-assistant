Local Agentic Research Assistant (AICC-230
Final)


A fully local research assistant. It answers questions from 29 various falconry PDFs.
using Ollama embeddings, MariaDB vector search, an MCP server, and an agent loop.

Nothing should leave the computer.

 software equirements:

    Python 
    MariaDB 11.7 or newer
    Ollama, with these models:
      Embeddings: nomic-embed-text (768 dimensions)
      Agent: qwen2.5 (or llama3.1 )
      (used qwen2.5 for project)

***********************
Setup
***********************
python -m venv .venv
.venv\Scripts\activate




[copy the following into an empty txt file named requirements.txt]

------------------------

mcp>=2.0.0
ddgs>=9.0.0
langchain-core
langchain-community
langchain-ollama
langchain-text-splitters
pypdf
pymysql
python-dotenv
tqdm
ollama
openai

------------------------------
***then***
------------------------------

pip install -r requirements.txt

-------------------------------

get

ollama pull nomic-embed-text
ollama pull qwen2.5
Pointing the project at MariaDB (or your DB)

-------------------------------

Make an .env and fill in your values.


DB_HOST=127.0.0.1
DB_PORT=3306 
DB_USER=" "
DB_PASSWORD=""
DB_NAME=""
DB_TABLE=AA""
OLLAMA_BASE_URL=http://localhost:11434
EMBED_MODEL=nomic-embed-text
EMBED_DIM=768
AGENT_MODEL=qwen2.5 (or the model of your choice)
MAX_ITERATIONS=""
CHUNK_SIZE=""
CHUNK_OVERLAP=""
TOP_K=""
DISTANCE_METRIC=cosine (optional)

__________________________________________________________
Create the table (run once in DBeaver or the mysql client)

Describe your table here and paste your real statements. It needs a

VECTOR(768) column, a short id key, and a vector index:

Re-running ingestion
1. Put the PDFs in [FOLDER NAME] (10 to 30 files, text PDFs, no scans).
2. To start clean, empty the table first ( clean_db.py or DELETE FROM
AAI_230_final_docs; ).
3. Run: python ingest.py ./[FOLDER NAME]
4. Check the result with python check_db.py (every file numbered and listed with a chunk count).
Running


__________________________________________________________

python rag_mcp_server.py --selftest "Your question about the material you sourced"

-starts self test
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
__________________________________________________________
python agent_demo_style.py

-The agent starts the MCP server itself. Type a question at the prompt; a blank line quits.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
*******************************************************************************************


How it works:

1. ingest.py splits each PDF into chunks, embeds them, and stores them in MariaDB.

2. rag_mcp_server.py exposes semantic_search(query, k) over MCP (stdio).

3. agent_demo_style.py runs a tool-calling loop (max [N] turns). The model searches,
        judges the results, may search again, then answers with citations (filename, page)
        or declines if the documents do not cover the question.

Document collection:

    [Number of PDFs(29 for mine)] PDFs. Short list of sources: [Utah Falconry Guide, New York Falconry Guide,
-- id must be short for vector indexes
************************************************************************************************

[IN SQL Scripts]
--this tells it where--
USE ragdb;
CREATE TABLE AAI_230_final LIKE lab2_pdfs;
--RUN THESE TWO TOGEATHER-- multiple line run alt+x --
------------^name of folder that holds PDFs^------------------------
--------------------------------^^sets it up like previos table^^---

(if table needs removed)
DROP TABLE 230_final;

ALTER TABLE AAI_230_final modify id char(64) character set ascii COLLATE ascii_bin NOT NULL;


--making the table how you need it (at least for this)
ALTER TABLE AAI_230_final ADD VECTOR INDEX (embedding) M=6 DISTANCE=cosine;
ALTER TABLE AAI_230_final_docs MODIFY id CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NALTER TABLE AAI_230_final_docs ADD VECTOR INDEX (embedding) M=6 DISTANCE=cosine;
...]
****************************************************************************************************

--------------------------------------------------------------------------------------
SAMPLE RUNS:

See transcripts/ : [1 normal answer], [1 correct decline], [1 multi-source question].

-------------------------------------------------------------------------------------
Known limitations:

    Chunks are large, so a hit can mix topics.
    No memory between questions.
    Some documents overlap (state rules for mine).