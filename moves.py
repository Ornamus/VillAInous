from game import CardType
import collections
from collections.abc import Iterable

class Move:
    
    def __init__(self, parent_action):
        self.parent_action = parent_action

    def perform(self, game_state, player):
        pass
	
    def __str__(self):
        return self.__class__.__name__

    def __eq__(self, other):
        return type(self) is type(other) and type(self.parent_action) is type(other.parent_action)
    
    def __ne__(self, other):
        return type(self) is not type(other) or type(self.parent_action) is not type(other.parent_action)

class EndTurnMove(Move):
    
    def __init__(self):
        super().__init__(None)
    
    def perform(self, game_state, player):
        pass
    
    def __str__(self):
        return "End Turn"

class MoveZoneMove(Move):

    def __init__(self, zone):
        super().__init__(None)
        self.zone = zone
    
    def perform(self, game_state, player):
        player.board_position = self.zone
 
    def __str__(self):
        return f"Move to zone {self.zone.number}"
        
    def __eq__(self, other):
        return type(self) is type(other) and self.zone == other.zone
    
    def __ne__(self, other):
        return type(self) is not type(other) or self.zone.number != other.zone.number

class PlayCardMove(Move):

    def __init__(self, card, parent_action, zone=None, target=None):
        super().__init__(parent_action)
        self.card = card
        self.zone = zone
        self.target = target
    
    def perform(self, game_state, player):
        if self.card.card_type is CardType.EFFECT or self.card.card_type is CardType.CONDITION:
            player.deck_discard.append(self.card)
        player.hand.remove(self.card)
        player.power -= self.card.cost
        self.card.play(player, game_state, target=self.target, zone=self.zone)
        
    def __str__(self):
        return f"Play card {self.card.name}"
                
    def __eq__(self, other):
        if type(self) is type(other) and self.card == other.card and self.zone == other.zone and self.target == other.target:
            if isinstance(self.target, Iterable) and isinstance(other.target, Iterable):
                return collections.Counter(self.target) == collections.Counter(other.target)
            else:
                return True
        return False
    
    def __ne__(self, other):
        return not self.__eq__(other)
        
class DiscardCardsMove(Move):
    
    def __init__(self, cards, parent_action):
        super().__init__(parent_action)
        self.cards = cards
        
    def perform(self, game_state, player):
        for card in self.cards:
            player.discard_card(card)

    def __str__(self):
        return f"Discard {len(self.cards)} cards"
    
    def __eq__(self, other):
        if type(self) is type(other):
            return collections.Counter(self.cards) == collections.Counter(other.cards)
                  
        return False
        
    def __ne__(self, other):
        return not self.__eq__(other)