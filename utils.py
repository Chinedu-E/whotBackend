import asyncio
from dataclasses import dataclass
import threading
from typing import Dict, List
from fastapi.websockets import WebSocket
import json

from game import Whot



    
@dataclass
class Session:
    id: int
    hostName: str
    numStartingCards: int
    numPlayers: int
    numAI: int
    timeLimit: int
    isPrivate: bool
    clients: List[tuple[WebSocket, int, str]]
    status: str = "waiting"  # "waiting", "starting",  "playing", "finished"
    current_turn_index: int = 0
    turns_played: int = 0
    

    async def add_client(self, client: WebSocket, client_id: int, name: str) -> bool:
        """
        Adds a client to the session.

        Parameters
        ----------
        client : WebSocket
            The websocket object to be added.
        client_id : int
            The ID of the client.

        Returns
        -------
        bool
            True if the client was successfully added, False otherwise.
        """
        if len(self.clients) == self.numPlayers:
            return False
        
        for client_ in self.clients:
            if client_[1]== client_id or client_[2]== name:
                return False
        self.clients.append((client, client_id, name))
        print("Added name: ",name, "to session:", self.id)
        return True
    
    async def remove_client(self, client_id):
        self.clients = list(filter(lambda x: x[1] != client_id, self.clients))
        data = {}
        if self.numPlayers > len(self.clients):
            player_cards = self.player_cards
            player_ids = [p['id'] for p in player_cards]
            client_ids = [c[1] for c in self.clients]
            left_match_ids = list(set(player_ids) - set(client_ids))
            new_cards = list(filter(lambda x: x['id'] not in left_match_ids, player_cards))
            if len(self.clients) == 1:
                data['winner'] = new_cards[0]['name']
                data['rankings'] = [[0, new_cards[0]['name']]]
                await self.broadcast_message(data)
                return
            data['player_cards'] = new_cards
            await self.broadcast_message(data)
            return
        
          
    async def broadcast_message(self, message):
        for client in self.clients:
            try:
                await client[0].send_json(message)
            except RuntimeError:
                ...
            except Exception as e:
                print(e)
                    
    async def process_game_move(self, move):
        if not move or len(move) == 0:
            return
        data = json.loads(move)
        last_stack = data['stack']
        data = self.game.process_game_move(data)
        
        self.turns_played += 1
        data['turns_played'] = self.turns_played
        data['last_stack'] = last_stack
        
        if self.numPlayers > len(self.clients):
            player_cards = self.player_cards
            player_ids = [p['id'] for p in player_cards]
            client_ids = [c[1] for c in self.clients]
            left_match_ids = list(set(player_ids) - set(client_ids))
            new_cards = list(filter(lambda x: x['id'] not in left_match_ids, player_cards))
            if len(self.clients) == 1:
                data['winner'] = player_cards[0]['name']
                data['rankings'] = [[0, player_cards[0]['name']]]
                await self.broadcast_message(data)
                return
            data['player_cards'] = new_cards
            
        self.player_cards = data['player_cards']
        
        await asyncio.sleep(0.25)
        
        if self.is_game_over(data):
            self.status = "game_over"
            await self.broadcast_message({'status': 'game_over', **data})
            clients = self.clients
            for client in clients:
                try:
                    await client[0].close()
                    self.clients.remove(client)
                except RuntimeError:
                    continue
            print("Game Over", data['winner'], "wins")
            
        await self.broadcast_message(data)
        
    def is_game_over(self, data):
        return data['winner'] != ''
                
    async def start_game(self):
        self.status = "starting"
        await self.broadcast_message({'status': 'starting'})
        await asyncio.sleep(3)
        
        self.game = Whot(clients=self.clients)
        
        cards = self.game.distribute_cards(self.numPlayers, self.numStartingCards)
        player_cards = [
            {
                'id': self.clients[i][1],
                'name': self.clients[i][-1],
                'hand': cards[i],
            }
            for i in range(len(self.clients))
        ]
        face_card = self.game.get_starting_card()
        data = {
            'player_cards': player_cards,
            'face_card': face_card,
            'turn': self.clients[0][1],
            'market': 0,
            'timePerTurn': self.timeLimit
        }
        self.player_cards = player_cards
        
        await self.broadcast_message(data)
        self.status = 'in-progress'
        await self.broadcast_message({'status': 'in-progress'})
   

class SessionsManager:
    """
    A class that manages sessions and their clients.

    Attributes:
        ids (Dict[int, Session]): A dictionary mapping session IDs to sessions.
        instance (SessionsManager): The singleton instance of the SessionsManager class.
    """

    ids: Dict[int, Session] = dict()
    instance = None

    def __init__(self):
        if SessionsManager.instance:
            self = SessionsManager.instance
        else:
            SessionsManager.instance = self
            
    def __getitem__(self, id: int) -> Session:
        return self.ids.get(id, None)

    def launch_session(self, id: int):
        """
        Launches a session with the given ID in a new thread.

        Args:
            id (int): The ID of the session to launch.
        """
        threading.Thread(target=self.__handle_session, args=(id,)).start()

    def __handle_session(self, id: int):
        """
        Handles a session in a new asyncio event loop in a separate thread.

        Args:
            id (int): The ID of the session to handle.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(self.handle_session(id))
        loop.close()
            
    async def handle_message(self, message: str, id: int):
        session = self.ids[id]
        await session.process_game_move(message)
        
    async def add_client(self, client: WebSocket, session_id: int, client_id: int, name: str) -> bool:
        """
        Adds a client to a session.

        Args:
            client (WebSocket): The client to add.
            session_id (int): The ID of the session to add the client to.
            client_id (int): The ID of the client to add.

        Returns:
            bool: True if the client was successfully added, False if the session is full.
        """
        return await self.ids[session_id].add_client(client, client_id, name)
    
    async def remove_client(self, session_id: int, client_id: int) -> bool:
        """
        Removes a client to a session.

        Args:
            client (WebSocket): The client to add.
            session_id (int): The ID of the session to add the client to.
            client_id (int): The ID of the client to add.

        Returns:
            bool: True if the client was successfully added, False if the session is full.
        """
        session = self.ids.get(session_id, None)
        if session:
            return await self.ids[session_id].remove_client(client_id)
        else: return False

    async def add_session(self, session: Session):
        """
        Adds a session to the manager.

        Args:
            session (Session): The session to add.
        """
        if session.id not in self.ids:
            self.ids[session.id] = session

    def is_done(self, id: int) -> bool:
        """
        Checks whether a session is done.

        Args:
            id (int): The ID of the session to check.

        Returns:
            bool: True if the session is done, False otherwise.
        """
        session = self.ids[id]
        return len(session.clients) <= 1

    def is_session_full(self, id: int) -> bool:
        """
        Checks whether a session is full.

        Args:
            id (int): The ID of the session to check.

        Returns:
            bool: True if the session is full, False otherwise.
        """
        session = self.ids.get(id, None)
        if session and session.numPlayers == len(session.clients):
            return True
        return False
    
    def delete_session(self, id: int):
        
        del self.ids[id]
        print("Deleted session:", id)
        
    def get_session_status(self, id: int) -> str:
        session = self.ids.get(id, None)
        return session.status
        
