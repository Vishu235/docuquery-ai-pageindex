import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from pageindex import PageIndexClient

load_dotenv()

CACHE_PATH = Path(".pageindex_doc_cache.json")
POLL_SECONDS = 5
MAX_ATTEMPTS = 60


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def file_fingerprint(file_name: str, file_bytes: bytes) -> str:
    digest = hashlib.sha256(file_bytes).hexdigest()
    return f"{file_name}:{digest}"


def wait_for_tree_ready(client: PageIndexClient, doc_id: str) -> None:
    for _ in range(MAX_ATTEMPTS):
        tree_data = client.get_tree(doc_id)
        if tree_data.get("status") == "completed":
            return
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"Document {doc_id} did not reach completed status in time.")


def wait_for_retrieval_ready(client: PageIndexClient, retrieval_id: str) -> dict:
    result = None
    for _ in range(MAX_ATTEMPTS):
        result = client.get_retrieval(retrieval_id)
        if result.get("status") == "completed":
            return result
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"Retrieval {retrieval_id} did not complete in time.")


def index_document(client: PageIndexClient, uploaded_file) -> str:
    file_bytes = uploaded_file.getvalue()
    cache_key = file_fingerprint(uploaded_file.name, file_bytes)

    cache = load_cache()
    cached_doc_id = cache.get(cache_key)
    if cached_doc_id:
        return cached_doc_id

    suffix = Path(uploaded_file.name).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        doc_info = client.submit_document(tmp_path)
        doc_id = doc_info["doc_id"]
        wait_for_tree_ready(client, doc_id)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    cache[cache_key] = doc_id
    save_cache(cache)
    return doc_id


def get_tree_preview(client: PageIndexClient, doc_id: str) -> list:
    tree_data = client.get_tree(doc_id, node_summary=True)
    tree_result = tree_data.get("result", [])
    if isinstance(tree_result, list):
        return tree_result
    return [tree_result]


def ask_question(client: PageIndexClient, doc_id: str, question: str) -> tuple[str, list]:
    retrieval_info = client.submit_query(doc_id, question)
    retrieval_result = wait_for_retrieval_ready(client, retrieval_info["retrieval_id"])
    reasoning_nodes = retrieval_result.get("result", [])

    response = client.chat_completions(
        messages=[{"role": "user", "content": question}],
        doc_id=doc_id,
    )
    answer = (
        response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "No answer returned.")
    )
    return answer, reasoning_nodes


def main() -> None:
    st.set_page_config(page_title="PageIndex PDF Q&A", layout="wide")
    st.title("PageIndex PDF Q&A")
    st.caption("Upload one or more PDFs, index them, and ask grounded questions.")

    api_key = os.getenv("PAGEINDEX_API_KEY")
    if not api_key:
        st.error("Missing PAGEINDEX_API_KEY in your .env file.")
        st.stop()

    client = PageIndexClient(api_key=api_key)

    uploaded_files = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if "doc_map" not in st.session_state:
        st.session_state.doc_map = {}

    if uploaded_files and st.button("Index uploaded files", type="primary"):
        with st.spinner("Submitting and indexing documents..."):
            for uploaded_file in uploaded_files:
                doc_id = index_document(client, uploaded_file)
                st.session_state.doc_map[uploaded_file.name] = doc_id
        st.success("Indexing complete.")

    if st.session_state.doc_map:
        st.subheader("Indexed documents")
        st.json(st.session_state.doc_map)

        selected_name = st.selectbox(
            "Choose a document",
            options=list(st.session_state.doc_map.keys()),
        )
        selected_doc_id = st.session_state.doc_map[selected_name]

        with st.expander("Document structure preview", expanded=False):
            with st.spinner("Loading structure..."):
                tree_preview = get_tree_preview(client, selected_doc_id)
            st.json(tree_preview)

        question = st.text_area(
            "Ask a question",
            placeholder="Example: What is the advantage of Transformer over RNNs for parallelization?",
        )

        if st.button("Get answer"):
            if not question.strip():
                st.warning("Please enter a question.")
            else:
                with st.spinner("Running retrieval and generating answer..."):
                    answer, reasoning_nodes = ask_question(client, selected_doc_id, question.strip())
                st.subheader("Answer")
                st.write(answer)

                st.subheader("Reasoning trace (retrieved nodes)")
                if reasoning_nodes:
                    for node in reasoning_nodes:
                        st.markdown(
                            f"- **Node {node.get('node_id', 'N/A')}**: {node.get('title', 'Untitled')}"
                        )
                else:
                    st.info("No explicit reasoning nodes were returned for this query.")


if __name__ == "__main__":
    main()
