# Knowledge Base Management Utilities

This directory contains utilities for managing knowledge bases for the Advanced Computing Team Collaboration Swarm.

## Files

- `kb_manager.py`: Core utility class for managing knowledge bases, uploading documents, and syncing
- `kb_upload.py`: Command-line tool for uploading and syncing documents
- `unsynced_docs.json`: Tracking file for unsynced documents (created automatically)

## Usage

### Command-Line Tool

The `kb_upload.py` script provides a command-line interface for managing knowledge bases:

```bash
# List knowledge bases and buckets
python kb_upload.py list

# Upload a file to a specific domain
python kb_upload.py upload --domain hpc --file /path/to/file.pdf

# Upload a directory of files to a specific domain
python kb_upload.py upload --domain quantum --directory /path/to/docs

# Upload files to all domains
python kb_upload.py upload --domain all --directory /path/to/docs

# List unsynced documents
python kb_upload.py unsynced

# Sync a specific domain
python kb_upload.py sync --domain genai

# Sync all domains
python kb_upload.py sync --domain all
```

### Web Interface

The Knowledge Base Manager is also available in the web app at `/Knowledge_Base_Manager`. This provides a user-friendly interface for:

1. Uploading documents to specific domains
2. Viewing unsynced documents
3. Syncing knowledge bases on demand

## Architecture

Each domain (HPC, Quantum, GenAI, etc.) has its own:
- S3 bucket for storing documents
- Bedrock Knowledge Base for vector search

This approach provides better isolation between domains and allows for more granular access control.

## Implementation Details

- Documents are uploaded to domain-specific S3 buckets
- Unsynced documents are tracked in `unsynced_docs.json`
- Syncing triggers an ingestion job in the Bedrock Knowledge Base
- The Knowledge Base Manager in the web app provides a user-friendly interface