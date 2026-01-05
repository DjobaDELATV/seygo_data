import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from ygojson.importers.yugipedia import YugipediaBatcher
import logging

# Configure logging to see what happens
logging.basicConfig(level=logging.INFO)

def fetch_skill():
    print("Fetching 'Balance'...")
    with YugipediaBatcher() as batcher:
        @batcher.getPageContents("Balance")
        def on_content(content):
            print("--- BEGIN CONTENT ---")
            print(content)
            print("--- END CONTENT ---")

if __name__ == "__main__":
    fetch_skill()
