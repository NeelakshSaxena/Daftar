import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mcp_adapter import read_file

def test_read_file_success():
    print("Testing read_file on existing file...")
    # This should succeed and return the contents of requirements.txt
    content = read_file("requirements.txt")
    if "fastapi" in content.lower():
        print("✅ Success: correctly read requirements.txt")
    else:
        print("❌ Failed: content did not match expectations")
        
def test_read_file_path_traversal():
    print("\nTesting read_file path traversal protection...")
    try:
        # Assuming the current working dir is the project root, this tries to access a directory above it
        read_file("../../../../../../etc/passwd")
        print("❌ Failed: Path traversal was allowed!")
    except PermissionError as e:
        print(f"✅ Success: Blocked path traversal. Caught exception: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected exception type: {type(e)}")

if __name__ == "__main__":
    test_read_file_success()
    test_read_file_path_traversal()
