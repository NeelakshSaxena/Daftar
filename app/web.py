from flask import Flask, request, jsonify
from app.memory.db import MemoryDB

app = Flask(__name__)
db = MemoryDB()

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

    return jsonify(memories)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
