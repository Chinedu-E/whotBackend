import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import HTMLResponse
from computer.bot import Bot
from utils import SessionsManager, Session
from fastapi.middleware.cors import CORSMiddleware
import json
import random

app = FastAPI()
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


def spawn_bots(n: int, session: Session):
    ...
        
session_manager = SessionsManager()


@app.get("/")
async def get():
    return HTMLResponse(html)



@app.post('/create/')
async def create(settings: str = Body(...)):
    settings = json.loads(settings)
    return int(random.random()*10000)

@app.websocket('/ws/games/')
async def get_games(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            games = []
            for id in session_manager.ids:
                session = session_manager[id]
                if session.isPrivate or session.status == "finished" or len(session.clients) == 0:
                    continue
                game = {
                    'id': id,
                    'private': session.isPrivate,
                    'host': session.hostName,
                    'status': session.status,
                    'max_players': session.numPlayers,
                    'num_players': len(session.clients),
                }
                games.append(game)
            
            await websocket.send_json({
                'games': games
            })
            
            await asyncio.sleep(1)  # Increased sleep time to reduce load
    except WebSocketDisconnect:
        print('Client disconnected')
    except Exception as e:
        print(f"An error occurred: {e}")
        
    
        


@app.websocket("/ws/create/{host_id}")
async def websocket_endpoint(websocket: WebSocket, host_id: str, id: int, settings: str):
    settings = json.loads(settings)
    print(settings)
    await websocket.accept()
    session = Session(id=id, **settings, clients=[])
    await session_manager.add_session(session)
    added = await session_manager.add_client(websocket, id, host_id, settings['hostName'])
    
    if not added:
        await websocket.close()
        return 'Already in game'
    
    bots: list[Bot] = []
    for _ in range(settings['numAI']):
        bot = Bot.create_bot(session.id, False)
        bots.append(bot)
        
    try:
        while True:
            if session_manager.is_session_full(session.id):
                session = session_manager[id]
                await session.start_game()
                print('Starting game')
                break
            await websocket.send_json({"status": "waiting"})
            await asyncio.sleep(0.1)  # Small sleep to prevent blocking
    except WebSocketDisconnect:
        print('disconnected')
        session_manager.delete_session(session.id)
        for bot in bots:
            bot.stop()
        return

    disconnected = False
    
    while not session_manager.is_done(session.id):
        try:
            text = await websocket.receive_text()
            await session_manager.handle_message(text, id)
        except WebSocketDisconnect:
            print('disconnected')
            disconnected = True
            break
        
    if disconnected:
        await session_manager.remove_client(session.id, host_id)
        session = session_manager.ids[session.id]
        if len(session.clients) == 0:
            session_manager.delete_session(session.id)
    else:
        session_manager.delete_session(session.id)
        
     # Stop all bots when the game is over
    for bot in bots:
        bot.stop()
    
    
    
@app.websocket("/ws/join/{session_id}")
async def join_game(websocket: WebSocket, client_id: str, session_id: int, display_name: str):
    await websocket.accept()
    
    added = await session_manager.add_client(websocket, session_id, client_id, display_name)
    if not added:
        print('Not added', session_id, client_id, display_name)
        status = session_manager.get_session_status(session_id)
        if status == 'in-progress':
            await websocket.send_json({"status": "full"})
        if status == 'starting':
            await websocket.send_json({"status": "started"})
        if status == 'finished':
            await websocket.send_json({"status": "finished"})
        await websocket.close()
        return
    
    while not session_manager.is_done(session_id):
        try:
            text = await websocket.receive_text()
            await session_manager.handle_message(text, session_id)
        except WebSocketDisconnect:
            print('disconnected')
            break
    await session_manager.remove_client(session_id, client_id)