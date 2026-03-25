# DocuQuery PageIndex

This project provides a Streamlit frontend for PageIndex where you can:

- Upload one or more PDF files
- Index them with PageIndex
- Select an indexed document
- Ask grounded questions against that document
- View retrieval reasoning nodes used by the system

## Files in this project

- `streamlit_app.py`: Streamlit user interface and PageIndex workflow
- `test_app.py`: CLI experiment script for direct API testing
- `TECHNICAL_DETAILS.md`: Technical explanation of PageIndex concepts and flow
- `.env`: Environment variables including your API key
- `.pageindex_doc_cache.json`: Local cache mapping uploaded file fingerprints to `doc_id`

## Prerequisites

- Python 3.10+
- A valid PageIndex API key

## Environment setup

1. Activate your virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set your API key in `.env`:

```env
PAGEINDEX_API_KEY=your_pageindex_api_key_here
```

## Run the app

```bash
streamlit run streamlit_app.py
```

## How to use

1. Upload one or more PDF files.
2. Click **Index uploaded files**.
3. Choose a document from the indexed list.
4. Optionally inspect **Document structure preview**.
5. Enter a question and click **Get answer**.

## Notes

- The app waits for tree status to become `completed` before allowing Q&A.
- The app stores a file hash cache in `.pageindex_doc_cache.json` to avoid re-uploading unchanged files.
- Retrieval node traces are displayed for transparency.
