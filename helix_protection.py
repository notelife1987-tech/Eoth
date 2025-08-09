# HELIX Ownership Protection - Termux Version
import hashlib
import json
import os
from datetime import datetime

def generate_ownership_proof():
    """Generate immutable proof of ownership using blockchain timestamp"""
    try:
        # Create hash of your critical files
        file_hashes = {}
        critical_files = ['app.py', 'config.json', 'requirements.txt']
        
        combined_hash = hashlib.sha256()
        
        for filename in critical_files:
            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    file_data = f.read()
                    file_hash = hashlib.sha256(file_data).hexdigest()
                    file_hashes[filename] = file_hash
                    combined_hash.update(file_data)
            else:
                print(f"Warning: {filename} not found")
        
        # Get latest blockchain block for timestamp
        response = requests.get("https://blockchain.info/latestblock", timeout=10)
        latest_block = response.json()
        
        # Create ownership proof
        proof_data = {
            'project': 'HELIX',
            'timestamp': datetime.now().isoformat(),
            'block_height': latest_block['height'],
            'block_hash': latest_block['hash'][:16],
            'code_hash': combined_hash.hexdigest(),
            'file_hashes': file_hashes,
            'creator': 'HELIX_DEV_FL',
            'version': '1.0'
        }
        
        # Create final proof hash
        proof_string = json.dumps(proof_data, sort_keys=True)
        final_proof = hashlib.sha256(proof_string.encode()).hexdigest()
        
        proof_data['proof_hash'] = final_proof
        
        return proof_data
        
    except Exception as e:
        print(f"Error generating proof: {e}")
        # Fallback proof without blockchain
        return {
            'project': 'HELIX',
            'timestamp': datetime.now().isoformat(),
            'code_hash': hashlib.sha256(b'HELIX_EMERGENCY_PROOF').hexdigest(),
            'creator': 'HELIX_DEV_FL',
            'version': '1.0',
            'note': 'Emergency proof - blockchain unavailable'
        }

def save_proof():
    """Save proof to multiple locations"""
    proof = generate_ownership_proof()
    
    # Save as JSON
    with open('HELIX_OWNERSHIP_PROOF.json', 'w') as f:
        json.dump(proof, f, indent=2)
    
    # Save as readable text
    with open('HELIX_OWNERSHIP_PROOF.txt', 'w') as f:
        f.write("=" * 50 + "\n")
        f.write("HELIX OWNERSHIP PROOF\n")
        f.write("=" * 50 + "\n")
        f.write(f"Project: {proof['project']}\n")
        f.write(f"Creator: {proof['creator']}\n")
        f.write(f"Timestamp: {proof['timestamp']}\n")
        f.write(f"Code Hash: {proof['code_hash']}\n")
        if 'block_height' in proof:
            f.write(f"Block Height: {proof['block_height']}\n")
            f.write(f"Block Hash: {proof['block_hash']}\n")
        f.write(f"Proof Hash: {proof.get('proof_hash', 'N/A')}\n")
        f.write("=" * 50 + "\n")
    
    return proof

if __name__ == '__main__':
    print("🔗 Generating HELIX Ownership Proof...")
    proof = save_proof()
    print("✅ Proof generated and saved!")
    print(f"📄 Files: HELIX_OWNERSHIP_PROOF.json, HELIX_OWNERSHIP_PROOF.txt")
    print(f"🔐 Your proof hash: {proof.get('proof_hash', 'N/A')}")
    
    # Quick verification
    if os.path.exists('HELIX_OWNERSHIP_PROOF.json'):
        print("✅ Proof files created successfully")
        print("💾 Backup these files immediately!")
        print("📧 Email them to yourself")
        print("☁️  Upload to cloud storage")
    else:
        print("❌ Error: Proof files not created")
