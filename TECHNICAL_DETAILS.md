# PageIndex Technical Details

This document explains what the PageIndex library does, the core API stages, and how the app integrates with it.

## What PageIndex does

PageIndex is a document understanding and retrieval API. For PDF workflows it provides:

1. **Document ingestion** (upload and process files)
2. **Tree generation** (hierarchical structural parsing of sections/nodes)
3. **Retrieval** (query-specific node selection)
4. **Answer generation** (chat completion grounded by selected document context)

## End-to-end lifecycle

### 1) Submit document

- API call: `client.submit_document(file_path)`
- Returns: `doc_id`
- Effect: Starts backend processing for structure and retrieval pipelines

### 2) Wait for tree completion

- API call: `client.get_tree(doc_id)`
- Key status field: `status`
- Expected progression: `queued` / `processing` → `completed`

Important: `retrieval_ready` may remain `False` even when `status` is `completed`. In practice, tree completion is sufficient for structural inspection and then query/retrieval APIs can be used.

### 3) Optional structure inspection

- API call: `client.get_tree(doc_id, node_summary=True)`
- Output: nested tree nodes with fields such as:
  - `node_id`
  - `title`
  - `page_index`
  - `text`
  - `nodes` (children)

This enables a frontend to show an interpretable structure preview.

### 4) Submit retrieval query

- API call: `client.submit_query(doc_id, question)`
- Returns: `retrieval_id`

This starts a retrieval job that identifies the most relevant document nodes for the user question.

### 5) Poll retrieval completion

- API call: `client.get_retrieval(retrieval_id)`
- Key status field: `status`
- Output on completion: retrieval result with selected/relevant nodes

These nodes are used as a transparent reasoning trace.

### 6) Generate final answer

- API call:

```python
client.chat_completions(
    messages=[{"role": "user", "content": question}],
    doc_id=doc_id,
)
```

- Behavior: runs a grounded answer generation step constrained by the indexed document context
- Response shape: OpenAI-style `choices[0].message.content`

## Why polling is needed

PageIndex processing is asynchronous. After submission/query initiation, backend jobs continue running. The client must poll `get_tree` and `get_retrieval` until `status == "completed"`.

Typical production-safe behavior:

- fixed polling interval (for example, 5s)
- max retry attempts / timeout
- clear timeout errors surfaced to users

## Streamlit app architecture in this project

`streamlit_app.py` implements:

1. **Upload layer**: accepts multiple PDFs
2. **Document cache**: stores file fingerprint (`name + sha256`) → `doc_id`
3. **Indexing layer**: submits only new/changed files
4. **Retrieval layer**: submits question and polls retrieval completion
5. **Generation layer**: calls `chat_completions` for final answer
6. **Transparency UI**: displays selected retrieval nodes

## Caching strategy details

- Cache file: `.pageindex_doc_cache.json`
- Key: `"<file_name>:<sha256(file_bytes)>"`
- Value: `doc_id`

This avoids re-uploading unchanged files while still re-indexing if the file content changes.

## Key fields used in responses

- Tree status: `tree_data["status"]`
- Tree content: `tree_data.get("result", [])`
- Retrieval status: `retrieval_data["status"]`
- Retrieval nodes: `retrieval_data.get("result", [])`
- Final answer: `chat_response["choices"][0]["message"]["content"]`

## Common pitfalls and fixes

1. **Infinite waiting on `retrieval_ready`**
   - Symptom: tree appears available but loop continues
   - Fix: wait on `status == "completed"` for tree stage

2. **Calling non-existent SDK methods**
   - Symptom: `AttributeError` for methods like `search_tree` / `generate_answer`
   - Fix: use supported sequence `submit_query` → `get_retrieval` → `chat_completions`

3. **Repeated re-uploading of same document**
   - Symptom: new `doc_id` on every run
   - Fix: fingerprint-based local cache

## Security and operational notes

- Keep API keys only in `.env` and never commit them.
- Large PDFs may need longer polling windows.
- Consider adding exponential backoff and detailed error telemetry for production.
