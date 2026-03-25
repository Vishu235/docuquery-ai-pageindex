import os
import asyncio
from dotenv import load_dotenv
from pageindex import PageIndexClient
import pageindex.utils as utils

# 1. Load variables from .env file
load_dotenv()

# 2. Initialize Clients
PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY")
if not PAGEINDEX_API_KEY:
    raise ValueError("Missing PAGEINDEX_API_KEY! Check your .env file.")

client = PageIndexClient(api_key=PAGEINDEX_API_KEY)

async def run_experiment(pdf_path, query):
    print(f"--- Indexing Document: {pdf_path} ---")
    
    # Phase 1: Submit and Wait (reuse doc_id if already submitted)
    cache_file = pdf_path + ".docid"
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            doc_id = f.read().strip()
        print(f"Reusing existing doc_id: {doc_id}")
    else:
        doc_info = client.submit_document(pdf_path)
        doc_id = doc_info["doc_id"]
        with open(cache_file, "w") as f:
            f.write(doc_id)
        print(f"Document submitted. doc_id: {doc_id}")

    max_attempts = 60  # 5 minutes max (60 x 5s)
    for attempt in range(max_attempts):
        tree_data = client.get_tree(doc_id)
        status = tree_data.get("status", "")
        print(f"[Attempt {attempt + 1}/{max_attempts}] status: {status}")
        if status == "completed":
            break
        print("Processing document structure (this may take a minute for large PDFs)...")
        await asyncio.sleep(5)
    else:
        raise TimeoutError(f"Document {doc_id} did not become ready after {max_attempts} attempts.")
    
    # Phase 2: Structural Retrieval
    tree_data = client.get_tree(doc_id, node_summary=True)
    tree = tree_data.get('result', tree_data) 
    
    print("\n[Inferred Document Structure]:")
    utils.print_tree(tree)

    # Phase 3: Submit retrieval query and wait for results
    print(f"\n--- Querying: '{query}' ---")
    retrieval_info = client.submit_query(doc_id, query)
    retrieval_id = retrieval_info["retrieval_id"]

    retrieval_result = None
    for attempt in range(max_attempts):
        retrieval_result = client.get_retrieval(retrieval_id)
        r_status = retrieval_result.get("status", "")
        print(f"[Retrieval attempt {attempt + 1}] status: {r_status}")
        if r_status == "completed":
            break
        await asyncio.sleep(5)
    else:
        raise TimeoutError(f"Retrieval {retrieval_id} did not complete in time.")

    # Print reasoning trace if available
    nodes = retrieval_result.get("result", [])
    if nodes:
        print("\n[Reasoning Trace]:")
        for node in nodes:
            print(f"-> Node {node.get('node_id', 'N/A')}: {node.get('title', 'Untitled')}")

    # Phase 4: Generate final answer via chat completions
    response = client.chat_completions(
        messages=[{"role": "user", "content": query}],
        doc_id=doc_id
    )
    answer = response.get("choices", [{}])[0].get("message", {}).get("content", "No answer returned.")
    print(f"\n--- FINAL ANSWER ---\n{answer}")

if __name__ == "__main__":
    # Path to your 'Attention Is All You Need' PDF
    PATH_TO_PDF = "Attention_RP.pdf" 
    QUERY = "Explain the advantage of the Transformer over RNNs in terms of parallelization."
    
    asyncio.run(run_experiment(PATH_TO_PDF, QUERY))