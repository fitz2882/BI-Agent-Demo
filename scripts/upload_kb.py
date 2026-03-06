"""Upload Knowledge Base files to a Google File Search store.

Usage:
    python scripts/upload_kb.py

This script:
1. Creates a new Google File Search store (or reuses an existing one)
2. Uploads all markdown files from knowledge_base/ into the store
3. Waits for indexing to complete
4. Prints the store name to add to your .env file

Requires GOOGLE_API_KEY to be set in .env or environment.
"""

import os
import sys
import time
import glob

from dotenv import load_dotenv
from google import genai

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

KB_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge_base")
STORE_DISPLAY_NAME = "acme-analytics-kb"
POLL_INTERVAL_SECONDS = 5
MAX_WAIT_SECONDS = 300  # 5 minutes


def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set. Add it to .env or export it.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # Collect KB files
    kb_files = sorted(glob.glob(os.path.join(KB_DIR, "*.md")))
    if not kb_files:
        print(f"ERROR: No .md files found in {KB_DIR}")
        sys.exit(1)

    print(f"Found {len(kb_files)} KB file(s):")
    for f in kb_files:
        print(f"  - {os.path.basename(f)}")

    # -----------------------------------------------------------------------
    # Check for existing store (reuse if found)
    # -----------------------------------------------------------------------
    existing_store = os.getenv("GOOGLE_FILE_SEARCH_STORE")
    if existing_store:
        print(f"\nGOOGLE_FILE_SEARCH_STORE already set: {existing_store}")
        print("Re-uploading files to existing store...")
        store_name = existing_store
    else:
        # Create a new File Search store
        print(f"\nCreating File Search store: {STORE_DISPLAY_NAME}")
        store = client.file_search_stores.create(
            config={"display_name": STORE_DISPLAY_NAME}
        )
        store_name = store.name
        print(f"Store created: {store_name}")

    # -----------------------------------------------------------------------
    # Upload each KB file
    # -----------------------------------------------------------------------
    operations = []
    for filepath in kb_files:
        filename = os.path.basename(filepath)
        print(f"\nUploading {filename}...")
        op = client.file_search_stores.upload_to_file_search_store(
            file=filepath,
            file_search_store_name=store_name,
            config={"display_name": filename},
        )
        operations.append((filename, op))
        print(f"  Upload started (operation: {op.name})")

    # -----------------------------------------------------------------------
    # Wait for all uploads to complete
    # -----------------------------------------------------------------------
    print("\nWaiting for indexing to complete...")
    start = time.time()
    pending = list(operations)

    while pending and (time.time() - start) < MAX_WAIT_SECONDS:
        still_pending = []
        for filename, op in pending:
            op = client.operations.get(op)
            if op.done:
                print(f"  {filename}: indexed")
            else:
                still_pending.append((filename, op))

        pending = still_pending
        if pending:
            time.sleep(POLL_INTERVAL_SECONDS)

    if pending:
        print("\nWARNING: Some files did not finish indexing within the timeout:")
        for filename, _ in pending:
            print(f"  - {filename}")
        print("They may still be processing. Check the Google AI Studio console.")

    # -----------------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("File Search store ready!")
    print(f"Store name: {store_name}")
    print()
    print("Add this to your .env file:")
    print(f"  GOOGLE_FILE_SEARCH_STORE={store_name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
