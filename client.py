from game import Whot
import pprint
import json



whot = Whot([])


cards = json.loads(json.dumps(whot.deck))

new_cards = [{
    'id': i,
    **cards[i]
} for i in range(len(cards))]




pprint.pprint(new_cards)