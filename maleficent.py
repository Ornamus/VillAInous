from game import Villian, Card, CardType, Character, CharacterType
import random

def dragon_form_effect(player_state, game_state):
    heroes = []
    for zone in player_state.board:
        for hero in zone.heroes:
            if hero.get_total_strength() <= 3:
                heroes.append((zone, hero))
    if len(heroes) == 0:
        return
    defeated = heroes[random.randint(0, len(heroes) - 1)]
    defeated[0].heroes.removed(defeated[1])
    player_state.fate_discard.append(defeated[1])

def vanish_effect(player_state, game_state):
    player_state.can_stay_on_zone = True

class MaleficentVillian(Villian):

    def generate_deck(self):
        deck = []
        for i in range(8):
            card = Card(3, "Generic Curse", CardType.CURSE)
            card.card_ally = Character(0, CharacterType.ALLY)
            deck.append(card)
        for i in range(3):
            card = Card(1, "Cackling Goon", CardType.ALLY)
            card.card_ally = CacklingGoon()
            deck.append(card)
            
            card = Card(3, "Dragon Form", CardType.EFFECT)
            card.targeted = True
            card.code = dragon_form_effect
            deck.append(card)
            
            card = Card(3, "Savage Goon", CardType.ALLY)
            card.card_ally = Character(4, CharacterType.ALLY)
            deck.append(card)
            
            card = Card(2, "Sinister Goon", CardType.ALLY)
            card.card_ally = SinisterGoon()
            deck.append(card)
            
            card = Card(0, "Vanish", CardType.EFFECT)
            card.code = vanish_effect
            deck.append(card)
        for i in range(2):
            card = Card(0, "Malice", CardType.CONDITION)
            deck.append(card)
            
            card = Card(0, "Tyranny", CardType.CONDITION)
            deck.append(card)
        
        card = Card(1, "Raven", CardType.ALLY)
        card.card_ally = Character(1, CharacterType.ALLY)
        deck.append(card)
        
        card = Card(1, "Spinning Wheel", CardType.ALLY) # CardType.ITEM
        card.card_ally = Character(0, CharacterType.ALLY)
        deck.append(card)
        
        card = Card(1, "Staff", CardType.ALLY) # CardType.ITEM
        card.card_ally = Character(0, CharacterType.ALLY)
        deck.append(card)
        return deck
    
    def get_score(self, player_state):
        curses = 0
        for zone in player_state.board:
            for ally in zone.allies:
                if ally.card_type == CardType.CURSE:
                    curses += 1
                    break
        return player_state.power + (curses * 6)
        
    def has_won(self, player_state):
        curses = 0
        for zone in player_state.board:
            for ally in zone.allies:
                if ally.card_type == CardType.CURSE:
                    curses += 1
                    break
        return curses >= 4
           
class CacklingGoon(Character):
    
    def __init__(self):
        super().__init__(1, CharacterType.ALLY)
        
    def get_total_strength(self, zone):
        total = super().get_total_strength(zone)
        total += len(zone.heroes)
        return total

class SinisterGoon(Character):

    def __init__(self):
        super().__init__(1, CharacterType.ALLY)
        
    def get_total_strength(self, zone):
        total = super().get_total_strength(zone)
        for ally in zone.allies:
            if ally.card_type == CardType.CURSE:
                total += 1
                break
        return total    
    