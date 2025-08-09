import hashlib
import os
from blockchain import blockexplorer

print("🛡️ Creating HELIX Protection Proof...")

# Generate SHA-256 of all code files
hasher = hashlib.sha256()
for root, dirs, files in os.walk("."):
 for fname in files:
 if fname.endswith(('.py', '.md', '.txt')):
 with open(fname, 'rb') as f:
 hasher.update(f.read())
digest = hasher.hexdigest()

# Get latest Bitcoin block
block = blockexplorer.get_latest_block()

# Save proof
with open('HELIX_PROOF.txt', 'w') as f:
 f.write(f"{digest}|{block.hash}|{block.height}")

print(f"""
✅ Proof Saved!
📍 Block Height: {block.height}
🖨️ Fingerprint: {digest[:12]}...{digest[-12:]}
""")
