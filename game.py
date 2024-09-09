from pydantic import BaseModel
import random
import json_fix



class Card(BaseModel):
    shape: str
    num: int
    
    def __json__(self):
        return self.__dict__
    
    def __getitem__(self, val):
        return self.__dict__.get(val, None)
    
    
deck_dict = {
    'cross': [1, 2, 3, 5, 7, 10, 11, 13, 14],
    'square': [1, 2, 3, 5, 7, 10, 11, 13, 14],
    'circle': [1, 2, 3, 4, 5, 7, 8, 10, 11, 12, 13, 14],
    'triangle': [1, 2, 3, 4, 5, 7, 8, 10, 11, 12, 13, 14],
    'star': [1, 2, 3, 4, 5, 7, 8]
}

class Whot:
    
    def __init__(self, clients):
        self.clients = clients
        self.deck = self.create_starting_deck()
        self.market: list[Card] = self.create_starting_deck()
        self.current_turn_index: int = 0
        
        
    def create_starting_deck(self):
        cards: list[Card] = []
        for shape, nums in deck_dict.items():
            shape_cards = [Card(shape=shape, num=num) for num in nums]
            cards += shape_cards
        random.shuffle(cards)
        return cards
    
    
    def distribute_cards(self, num_players: int, num_starting_cards: int):
        hands = [self.generate_hand(num_starting_cards) for _ in range(num_players)]
        return hands
            
    def generate_hand(self, n: int, no_action: bool = False) -> list[Card]:
        actions = [1, 2, 5, 8, 14, 20]
        hand = []
        while True:
            if n >= len(self.deck):
                self.deck = self.create_starting_deck()
                
            if len(hand) == n:
                break
            
            card = self.deck.pop(0)
            if no_action and card.num in actions:
                self.deck.append(card)
                continue
            hand.append(card)
        return hand
    
    def get_starting_card(self) -> Card:
        card = self.generate_hand(1, no_action=True)[0]
        return card
    
    def process_game_move(self, move):
        if move['face_card']['num'] in [2, 5] and move['market'] > 1:
            if move['failed_defense']:
                turn = move['turn']
            else:
                next_turn = self.get_next_turn()
                turn = next_turn
            player = [(i, p) for (i, p) in enumerate(move['player_cards']) if p['id'] == turn][0]
            rest = [p for p in move['player_cards'] if p['id'] != turn]
            defence = list(filter(lambda x: x['num'] in [move['face_card']['num'], 20] ,player[1]['hand']))
            cannot_defend = len(defence) == 0
            if cannot_defend or move['failed_defense']:
                # Add cards to player since cant defend
                cards = self.generate_hand(move['market'])
                player[1]['hand'] += cards
                # Now skip turn
                next_turn = self.get_next_turn()
                turn = next_turn
            rest.insert(player[0], player[1])
            return {
                'player_cards': rest,
                'face_card': move['face_card'],
                'turn': turn,
                'market': 0 if (cannot_defend or move['failed_defense']) else move['market'],
                'winner': self.get_winner(rest),
                'rankings': self.rank_players(rest)
            }
                
        if move['face_card']['num'] == 14 and move['market'] != 1: # Gen market (if only 1, market is 0 otherwise the amount stacked)
            turn = move['turn']
            player = [(i, p) for (i, p) in enumerate(move['player_cards']) if p['id'] == turn][0]
            rest = [p for p in move['player_cards'] if p['id'] != turn]
            for i in range(len(rest)):
                cards = self.generate_hand(1 if move['market'] == 0 else move['market'])
                rest[i]['hand'] += cards
            rest.insert(player[0], player[1])
            return {
                'player_cards': rest,
                'face_card': move['face_card'],
                'turn': turn,
                'market': 0,
                'winner': self.get_winner(rest),
                'rankings': self.rank_players(rest)
            }
            
        if move['face_card']['num'] == 14 and move['market'] == 1: # After gen market, cant play
            turn = move['turn']
            player = [(i, p) for (i, p) in enumerate(move['player_cards']) if p['id'] == turn][0]
            rest = [p for p in move['player_cards'] if p['id'] != turn]
            cards = self.generate_hand(move['market'])
            player[1]['hand'] += cards
            rest.insert(player[0], player[1])
            next_turn = self.get_next_turn()
            turn = next_turn
            return {
                'player_cards': rest,
                'face_card': move['face_card'],
                'turn': turn,
                'market': 0,
                'winner': self.get_winner(rest),
                'rankings': self.rank_players(rest)
            }
            
        if move['face_card']['num'] == 8 and move['market'] == 0: # Skip next player(s) simple
            for _ in range(move['turns_to_skip']):
                next_turn = self.get_next_turn()
            turn = next_turn
            return {
                'player_cards': move['player_cards'],
                'face_card': move['face_card'],
                'turn': turn,
                'market': 0,
                'winner': self.get_winner(move['player_cards']),
                'rankings': self.rank_players(move['player_cards'])
            }
            
        if move['face_card']['num'] == 8 and move['market'] == 1: # next player after the skipped, cant play
            turn = move['turn']
            cards = self.generate_hand(move['market'])
            player = [(i, p) for (i, p) in enumerate(move['player_cards']) if p['id'] == turn][0]
            rest = [p for p in move['player_cards'] if p['id'] != turn]
            player[1]['hand'] += cards
            rest.insert(player[0], player[1])
            next_turn = self.get_next_turn()
            turn = next_turn
            return {
                'player_cards': rest,
                'face_card': move['face_card'],
                'turn': turn,
                'market': 0,
                'winner': self.get_winner(rest),
                'rankings': self.rank_players(rest)
            }
            
        if move['face_card']['num'] == 1 and move['market'] == 0:
            return {
                'player_cards': move['player_cards'],
                'face_card': move['face_card'],
                'turn': move['turn'],
                'market': 0,
                'winner': self.get_winner(move['player_cards']),
                'rankings': self.rank_players(move['player_cards'])
            }
        
        if move['face_card']['num'] == 1 and move['market'] == 1:
            turn = move['turn']
            cards = self.generate_hand(move['market'])
            player = [(i, p) for (i, p) in enumerate(move['player_cards']) if p['id'] == turn][0]
            rest = [p for p in move['player_cards'] if p['id'] != turn]
            player[1]['hand'] += cards
            rest.insert(player[0], player[1])
            next_turn = self.get_next_turn()
            turn = next_turn
            return {
                'player_cards': rest,
                'face_card': move['face_card'],
                'turn': turn,
                'market': 0,
                'winner': self.get_winner(rest),
                'rankings': self.rank_players(rest)
            }
        
             
        turn = move['turn']
        cards = self.generate_hand(move['market'])
        player = [(i, p) for (i, p) in enumerate(move['player_cards']) if p['id'] == turn][0]
        rest = [p for p in move['player_cards'] if p['id'] != turn]
        player[1]['hand'] += cards
        rest.insert(player[0], player[1])
        next_turn = self.get_next_turn()
        turn = next_turn
            
        return {
            'player_cards': rest,
            'face_card': move['face_card'],
            'turn': turn,
            'market': 0,
            'winner': self.get_winner(rest),
            'rankings': self.rank_players(rest)
        }
            
    
    def get_winner(self, players):
        if len(players) == 1:
            return players[0]['name']
        player = list(filter(lambda x: len(x['hand']) == 0, players))
        if len(player) == 0:
            return ''
        return player[0]['name']
    
    def rank_players(self, players):
        data = []
        for player in players:
            total = 0
            for card in player['hand']:
                total += dict(card)['num']
            data.append([total, player['name']])
        return sorted(data, key = lambda x: x[0])
    
    def get_next_turn(self):
        self.current_turn_index = (self.current_turn_index + 1) % len(self.clients)
        return self.clients[self.current_turn_index][1]
    
    
    
def is_valid(face_card: dict, to_play: dict, has_played: bool) -> bool:
    # Special case: Whot card (represented by shape 20) can be played on any card
    if to_play['shape'] == 20:
        return True

    if has_played:
        if to_play['num'] == face_card['num']:
            return True
        return False

    # Match by shape
    if to_play['shape'] == face_card['shape']:
        return True

    # Match by number
    if to_play['num'] == face_card['num']:
        return True

    # Special cards logic
    if face_card['num'] == 1:  # Pick One
        return to_play['num'] == 1
    elif face_card['num'] == 2:  # Pick Two
        return to_play['num'] == 2
    elif face_card['num'] == 5:  # Pick Three
        return to_play['num'] == 5
    elif face_card['num'] == 8:  # Suspension
        return to_play['num'] == 8
    elif face_card['num'] == 14:  # General Market
        return to_play['num'] == 14

    # If none of the above conditions are met, the card is not valid
    return False


def get_stack_value(stack: list, market: int) -> dict:
    value = 0
    turns_to_skip = 1
    failed_defense = False
    card = stack[0] if len(stack) > 0 else None
    
    if card:
        if card['num'] == 2:
            value = 2 * len(stack)
        elif card['num'] == 5:
            value = 3 * len(stack)
        elif card['num'] == 14:
            value = 0 if len(stack) == 1 else (1 * len(stack))
        elif card['num'] == 8:
            turns_to_skip = 1 * len(stack)

    if len(stack) == 0 and market > 0:
        failed_defense = True
    

    return {
        'market': market + value,
        'turns_to_skip': 2 if turns_to_skip == 1 else turns_to_skip + 1,
        'failed_defense': failed_defense
    }
