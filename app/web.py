import os
import sys

# Add the project root to sys.path so 'app.memory.db' resolves even if run from 'app/' dir
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from app.memory.db import MemoryDB

app = Flask(__name__)
db = MemoryDB()

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "online",
        "message": "Welcome to the Daftar Memory Engine. Please navigate to /memories?user_id=YOUR_USER_ID to view your active memories."
    })

@app.route("/memories", methods=["GET"])
def get_memories():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    memories = db.retrieve_memories(
        user_id=user_id,
        state_filter="active",
        limit=20
    )

    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Daftar Memory Engine</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f7; color: #1d1d1f; margin: 0; padding: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { font-size: 28px; font-weight: 600; margin-bottom: 30px; }
            .memory-card { background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
            .memory-content { font-size: 18px; line-height: 1.5; margin-bottom: 16px; }
            .meta-tags { display: flex; gap: 10px; flex-wrap: wrap; }
            .tag { background: #e8e8ed; padding: 4px 10px; border-radius: 16px; font-size: 13px; font-weight: 500; color: #515154; }
            .tag.subject { background: #e3f2fd; color: #1565c0; }
            .tag.source { background: #f3e5f5; color: #6a1b9a; }
            .empty { text-align: center; color: #86868b; font-size: 18px; margin-top: 60px; }
            .user-info { margin-bottom: 40px; color: #86868b; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧠 Active Memories</h1>
            <div class="user-info">Viewing memory span for: <strong>{user_id}</strong></div>
            
            {cards}
        </div>
    </body>
    </html>
    '''
    
    if not memories:
        cards = '<div class="empty">No active memories found for this user.</div>'
    else:
        cards = ""
        for m in memories:
            cards += f'''
            <div class="memory-card">
                <div class="memory-content">{m['content']}</div>
                <div class="meta-tags">
                    <span class="tag subject">🏷️ {m['subject']}</span>
                    <span class="tag">Confidence: {m['confidence_score']}</span>
                    <span class="tag source">Source: {m['source']}</span>
                    <span class="tag">📅 {m['created_at']}</span>
                </div>
            </div>
            '''
            
    return html.replace('{user_id}', user_id).replace('{cards}', cards)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
