"""
Reset ChromaDB database - Use this if you encounter metadata compatibility issues
This will delete all vector data and recreate the database
"""
import os
import shutil
from pathlib import Path

# Get the project root (assuming script is in backend/scripts/)
backend_dir = Path(__file__).parent.parent
chroma_db_path = backend_dir / "data" / "chroma_db"

print("=" * 50)
print("ChromaDB Reset Script")
print("=" * 50)
print(f"\nThis will delete all data in: {chroma_db_path}")
print("WARNING: This will delete all vector embeddings!")
print("\nYou will need to re-upload and re-ingest all documents after this.")
print("\nDo you want to continue? (yes/no): ", end="")

response = input().strip().lower()
if response != "yes":
    print("Cancelled.")
    exit(0)

# Delete ChromaDB directory
if chroma_db_path.exists():
    try:
        # Delete all files in chroma_db directory
        for file in chroma_db_path.iterdir():
            if file.is_file():
                file.unlink()
                print(f"Deleted: {file.name}")
        print(f"\n✓ ChromaDB database reset complete!")
        print("You can now restart the backend server.")
    except Exception as e:
        print(f"\n✗ Error resetting ChromaDB: {e}")
        exit(1)
else:
    print(f"\nChromaDB directory not found at {chroma_db_path}")
    print("Nothing to reset.")



