import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion.parsers.web_parser import WebParser
from src.ingestion.chunking import AdaptiveChunker

url_to_test = "https://vi.wikipedia.org/wiki/Tr%C3%AD_tu%E1%BB%87_nh%C3%A2n_t%E1%BA%A1o"
web_parser = WebParser()
document_tree = web_parser.parse(url_to_test)

chunker = AdaptiveChunker()
chunks = chunker.process_document(document_tree)

print("Number of chunks:", len(chunks))
print("First chunk keys:", chunks[0].keys())
print("First chunk metadata:", chunks[0]["metadata"])

# Check for recursion/circularity in metadata
import json
try:
    json.dumps(chunks[0]["metadata"])
    print("Metadata is JSON serializable!")
except Exception as e:
    print("Metadata NOT JSON serializable:", e)

# Let's inspect if any metadata has circular references
def check_circular(d, path=""):
    if isinstance(d, dict):
        for k, v in d.items():
            check_circular(v, f"{path}.{k}")
    elif isinstance(d, list):
        for idx, item in enumerate(d):
            check_circular(item, f"{path}[{idx}]")
    else:
        # Check if it's a complex object
        if hasattr(d, "__dict__"):
            print(f"Found object at {path}: {type(d)}")

for i, chunk in enumerate(chunks):
    check_circular(chunk["metadata"], f"chunk[{i}].metadata")
