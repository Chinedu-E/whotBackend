import asyncio 
import json
import os
import random
import threading
import websockets
from dotenv import load_dotenv

from game import get_stack_value, is_valid

load_dotenv()

backend = os.getenv('BACKEND')
class Bot:
    
    def __init__(self, host: bool):
        self.host_ = host
        self._stop_event = threading.Event()
        self.thread = None
        self.loop = None
        
    
    async def start_bot(self, session_id: str, host: bool, settings: str = None):
        id = str(int(random.random()*10000))
        if host:
            await self.host(id, session_id, settings)
        else:
            await self.connect(id, session_id)
        
    @staticmethod
    def create_bot(session_id: str, host: bool, settings: str = None):
        bot = Bot(host)
        bot.start(session_id, host, settings)
        return bot
        
    def run_in_thread(self, session_id: str, host: bool, settings: str = None):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.task = self.loop.create_task(self.start_bot(session_id, host, settings))
        try:
            self.loop.run_until_complete(self.task)
        except asyncio.CancelledError:
            pass
        finally:
            self.loop.close()

    def start(self, session_id: str, host: bool, settings: str = None):
        self.thread = threading.Thread(target=self.run_in_thread, args=(session_id, host, settings))
        self.thread.start()

    def stop(self):
        if self.thread and self.thread.is_alive():
            self._stop_event.set()
            if self.loop and self.task:
                self.loop.call_soon_threadsafe(self.task.cancel)
            self.thread.join(timeout=7)
            if self.thread.is_alive():
                print("Bot thread did not terminate within the expected time.")
            
    async def host(self, id: str, session_id: str, settings:str):
        settings = (settings.replace("\"", '%22').replace(" ", ''))
        url = f"{backend}/ws/create/{id}?id={session_id}&settings={settings}"
        try:
            async with websockets.connect(url)\
                                        as websocket:
                async for message in websocket:
                    try:
                        move = json.loads(message)
                        data = self.process(move, id)
                        if data:
                            await websocket.send(json.dumps(data))
                    except websockets.exceptions.ConnectionClosedError:
                        break
        except websockets.exceptions.ConnectionClosedError:
            return
            
    async def connect(self, id: str, session_id: str):
        try:
            async with websockets.connect(f"{backend}/ws/join/{session_id}?client_id={id}&display_name=bot_{id}")\
                                        as websocket:
                self.websocket = websocket
                async for message in websocket:
                    try:
                        move = json.loads(message)
                        data = self.process(move, id)
                        if data:
                            await asyncio.sleep(0.25)
                            await websocket.send(json.dumps(data))
                    except websockets.exceptions.ConnectionClosedError:
                        break
        except websockets.exceptions.ConnectionClosedError:
            return
        
    def process(self, move: dict, id: str) :
        if 'winner' in move and move['winner'] != '':
            return
        
        if 'turn' in move and move['turn'] == id:
            player = [(i, p) for (i, p) in enumerate(move['player_cards']) if p['id'] == move['turn']][0]
            d, new_hands, stack = get_a_move(move['face_card'], player[1]['hand'], move['market'])
            player[1]['hand'] = new_hands
            rest = [p for p in move['player_cards'] if p['id'] != move['turn']]
            rest.insert(player[0], player[1])
            if len(stack) == 0:
                d['market'] = 1
            return {
                'player_cards': rest,
                'stack': stack,
                'face_card': move['face_card'] if len(stack) == 0 else stack[-1],
                'turn': move['turn'],
                **d
            }
        
    
    
def get_a_move(face_card: dict, hand_cards: list, market: int):
    stack = []
    new_hands = hand_cards
    for card in sorted(hand_cards, key = lambda x: x['num']):
        valid_move = is_valid(face_card if len(stack) == 0 else stack[-1], 
                              card, len(stack) > 0)
        if valid_move:
            stack.append(card)
            new_hands.remove(card)
    return get_stack_value(stack, market), new_hands, stack
        
    
def get_self(move, id: str) :
    player = list(filter(lambda x: x['id'] == id,move['player_cards']))
    return player[0] if len(player) > 0 else None
    
    
