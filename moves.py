from game import CardType, PowerAction
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
        player.board_position = player.board[self.zone.number]
 
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
        self.card.play(player, game_state, target=self.target, zone=player.board[self.zone.number] if self.zone else None)
        
    def __str__(self):
        if self.zone and not self.target:
            return f"Play {self.card.name} to zone {self.zone.number}"
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

class MoveAllyMove(Move):
    
    def __init__(self, ally, prev_zone, zone, parent_action):
        super().__init__(parent_action)
        self.ally = ally
        self.prev_zone = prev_zone.number
        self.zone = zone.number
    
    def perform(self, game_state, player):
        if self.ally.card_type == CardType.ALLY:
            player.board[self.prev_zone].allies.remove(self.ally)
            player.board[self.zone].allies.append(self.ally)
        elif self.ally.card_type == CardType.ITEM:
            player.board[self.prev_zone].items.remove(self.ally)
            player.board[self.zone].items.append(self.ally)
        
    def __str__(self):
        return f"Move {self.ally.name} to zone {self.zone}"    
        
    def __eq__(self, other):
        return type(self) is type(other) and self.ally == other.ally and self.prev_zone == other.prev_zone and self.zone == other.zone
        
    def __ne__(self, other):
        return not self.__eq__(other)

class VanquishMove(Move):

    def __init__(self, allies, hero, zone, parent_action):
        super().__init__(parent_action)
        self.allies = allies
        self.hero = hero
        self.zone = zone.number        

    def perform(self, game_state, player):
        for ally in self.allies:
            player.board[self.zone].allies.remove(ally)     
            player.deck_discard.append(ally)
        player.board[self.zone].heroes.remove(self.hero)
        player.fate_discard.append(self.hero)
        
        if len(player.board[self.zone].heroes) == 0:
            for action in player.board[self.zone].actions_blockable:
                if type(action) is PowerAction and action not in game_state.actions_used:
                    player.power += action.power
                    print("freed power")
                    actions_used.append(action)
        
    def __str__(self):
        if len(self.allies) == 1:
            return f"Vanquish {self.hero.name} with {self.allies[0].name}"
        else:
            return f"Vanquish {self.hero.name} with {len(self.allies)} allies"
        
    def __eq__(self, other):
        if type(self) is type(other) and self.hero == other.hero and self.zone == other.zone:
            return collections.Counter(self.allies) == collections.Counter(other.allies)
        return False
        
    def __ne__(self, other):
        return not self.__eq__(other)
        
class FateMove(Move):

    def __init__(self, target_player, parent_action):
        super().__init__(parent_action)
        self.target_player_index = target_player
    
    def perform(self, game_state, player):
        target_player = game_state.players[self.target_player_index]    
        fate_card = target_player.get_fate_card()
        target_player.fate_discard.append(target_player.get_fate_card())           
        if fate_card.card_type == CardType.ALLY:
            heroes = 0
            for zone in target_player.board:
                heroes += len(zone.heroes)
            if (heroes >= 1 and len(target_player.board[3].heroes) == 0) or heroes == 1:
                target_player.board[3].heroes.append(fate_card)
            else:
                target_player.board_position.heroes.append(fate_card)
        else:
            if fate_card.card_type == CardType.EFFECT:
                fate_card.play(target_player, game_state)
            target_player.fate_discard.append(fate_card)
            
    def __str__(self):
        return f"Fate player {self.target_player_index}"
        
    def __eq__(self, other):
        return type(self) is type(other) and self.target_player_index == other.target_player_index
        
    def __ne__(self, other):
        return type(self) is not type(other) or self.target_player_index != other.target_player_index