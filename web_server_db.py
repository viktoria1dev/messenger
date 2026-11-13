from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
import sqlite3
from datetime import datetime

app = FastAPI()
clients = []

# --- База данных ---
def init_db():
    conn = sqlite3.connect("chat.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            text TEXT,
            time TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_message(username, text):
    conn = sqlite3.connect("chat.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (username, text, time) VALUES (?, ?, ?)",
        (username, text, datetime.now().strftime("%H:%M"))
    )
    conn.commit()
    conn.close()

def get_last_messages(limit=50):
    conn = sqlite3.connect("chat.db")
    cur = conn.cursor()
    cur.execute("SELECT username, text, time FROM messages ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return list(reversed(rows))

init_db()

# --- HTML ---
html = """
<!DOCTYPE html>
<html>
<head>
    <title>Мой мессенджер</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial; max-width: 600px; margin: 20px auto; }
        #messages { border: 1px solid #ccc; height: 400px; overflow-y: scroll;
                    padding: 10px; margin-bottom: 10px; background: #f9f9f9; }
        #msg { width: 60%; padding: 8px; }
        #name { width: 20%; padding: 8px; }
        button { padding: 8px 15px; }
        .my { color: blue; }
        .other { color: green; }
        .time { color: #888; font-size: 12px; }
    </style>
</head>
<body>
    <h2>Мой мессенджер 💬</h2>
    <div>
        <input id="name" placeholder="Твоё имя" value="Гость">
        <input id="msg" placeholder="Сообщение..." autocomplete="off">
        <button onclick="sendMessage()">Отправить</button>
    </div>
    <div id="messages"></div>

    <script>
        const ws = new WebSocket("ws://" + location.host + "/ws");
        const messages = document.getElementById("messages");
        const input = document.getElementById("msg");
        const nameInput = document.getElementById("name");
        fetch("/history")
            .then(res => res.json())
            .then(data => {
                data.forEach(m => addMessage(m[0], m[1], m[2], false));
            });

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            addMessage(data.username, data.text, data.time, false);
        };

        function addMessage(username, text, time, isMine) {
            const div = document.createElement("div");
            div.className = isMine ? "my" : "other";
            div.innerHTML = `<b>${username}</b> <span class="time">${time}</span><br>${text}`;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        function sendMessage() {
            const text = input.value.trim();
            const username = nameInput.value.trim() || "Гость";
            if (text === "") return;
            const payload = { username: username, text: text };
            ws.send(JSON.stringify(payload));
            addMessage(username, text, new Date().toLocaleTimeString().slice(0,5), true);
            input.value = "";
        }

        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.get("/history")
async def history():
    return get_last_messages()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            import json
            msg = json.loads(data)
            username = msg.get("username", "Гость")
            text = msg.get("text", "")
            time_str = datetime.now().strftime("%H:%M")
            save_message(username, text)
            payload = json.dumps({"username": username, "text": text, "time": time_str}, ensure_ascii=False)
            for client in clients:
                if client != websocket:
                    try:
                        await client.send_text(payload)
                    except:
                        pass
    except WebSocketDisconnect:
        clients.remove(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)