from game import *

class CaptainHook(Villain):

    def generate_deck(self):
        deck = []
        # Three Copies
        for i in range(0, 3):
            card = Card(2, "Boarding Party", CardType.ALLY)
            card.card_ally = Character(2, CharacterType.ALLY)
            card.card_ally.adjacent_vanquish = True
            deck.append(card)
            
            # TODO: Look at 2 top cards of fate deck, discard both or return them in any order.
            card = Card(2, "Give Them A Scare", CardType.EFFECT)
            deck.append(card)
            
            card = Card(1, "Swashbuckler", CardType.ALLY)
            card.card_ally = Character(2, CharacterType.ALLY)
            deck.append(card)
            
            card = Card(0, "Worthy Opponent", CardType.EFFECT)
            card.code = worthy_opponent
            deck.append(card)
        
        # Two Copies
        for i in range(1, 3):
            # TODO: Move ally to adjacent unlocked zone, +2 strength till end of turn
            card = Card(1, "Aye Aye, Sir!", CardType.EFFECT)
            deck.append(card)
            
            card = Card(2, "Cannon", CardType.ITEM)
            card.actions_granted.append(VanquishAction(number=-i))
            deck.append(card)
            
            #card = Card(0, "Cunning", CardType.CONDITION)
            #deck.append(card)
            
            card = Card(1, "Cutlass", CardType.ITEM)
            card.equip = True
            card.strength_bonus = 1
            deck.append(card)
            
            card = Card(2, "Hook's Case", CardType.ITEM)
            card.actions_granted.append(PowerAction(1, number=-i))
            deck.append(card)
            
            #card = Card(0, "Obsession", CardType.CONDITION)
            #deck.append(card)
            
            card = Card(3, "Pirate Brute", CardType.ALLY)
            card.card_ally = Character(4, CharacterType.ALLY)
            deck.append(card)
            
        # One Copy
        card = Card(2, "Ingenius Device", CardType.ITEM)
        card.actions_granted.append(MoveHeroAction(number=-i))
        deck.append(card)
        
        # TODO: When played, you may move a hero from his zone to an adjacent unlocked zone
        card = Card(2, "Mr. Starkey", CardType.ALLY)
        card.card_ally = Character(2, CharacterType.ALLY)
        deck.append(card)
        
        card = Card(4, "Neverland Map", CardType.ITEM)
        card.code = neverland_map
        deck.append(card)        
        return deck

    def generate_fate(self):
        fate = []
        
        for i in range(0, 3):
            card = Card(0, "Pixie Dust", CardType.ITEM)
            card.equip = True
            card.strength_bonus = 2
            card.fate = True
            fate.append(card)
            
        for i in range(0, 2):
            # TODO: Two allies minimum to vanquish
            card = Card(0, "Lost Boys", CardType.ALLY)
            card.card_ally = Character(4, CharacterType.HERO)
            card.fate = True
            fate.append(card)
            
            card = Card(0, "Splitting Headache", CardType.EFFECT)
            #card.targeted = True
            #card.target_set = splitting_headache_targets
            #card.code = splitting_headache
            card.fate = True
            fate.append(card)
            
            # TODO: Taunt effect, must be defeated before any other heroes
            card = Card(0, "Taunt", CardType.ITEM)
            card.equip = True           
            fate.append(card)
        
        # TODO: +1 strength if there are any items attached
        card = Card(0, "John", CardType.ALLY)
        card.card_ally = Character(2, CharacterType.HERO)
        card.fate = True
        fate.append(card)
        
        # TODO: +1 strength for each location with a Hero, this included
        card = Card(0, "Michael", CardType.ALLY)
        card.card_ally = Character(1, CharacterType.HERO)
        card.fate = True
        fate.append(card)
        
        # TODO: Force played out of the two options, must be played to board[3], and death has to be tracked
        card = Card(0, "Peter Pan", CardType.ALLY)
        card.card_ally = Character(8, CharacterType.HERO)
        card.fate = True
        fate.append(card)
        
        # TODO: Hook discards hand if he moves to this location
        card = Card(0, "Tick Tock", CardType.ALLY)
        card.card_ally = Character(5, CharacterType.HERO)
        card.fate = True
        fate.append(card)
        
        # TODO: when played, may discard one ally from her location
        card = Card(0, "Tinker Bell", CardType.ALLY)
        card.card_ally = Character(2, CharacterType.HERO)
        card.fate = True
        fate.append(card)
        
        # TODO: aura, all other heroes in the realm get +1 strength
        card = Card(0, "Wendy", CardType.ALLY)
        card.card_ally = Character(3, CharacterType.HERO)
        card.fate = True
        fate.append(card)
        return fate
        
    def has_won(self, player_state):
        for card in player_state.vanquish_history:
            if card.name == "Peter Pan":
                return True
        return False
    
def worthy_opponent(player, game_state):
    from moves import PlayCardMove
    player.add_power(2)
    return
    while True:
        card = player.get_fate_card()
        if card.card_ally and card.card_ally.card_ally_type == CharacterType.HERO:
            if card.name == "Peter Pan":
                card.play(player, game_state, zone=player.board[3])
                break
            else:
                moves = []
                for zone in player.board:
                    moves.append(PlayCardMove(card, None, zone=zone))
                game_state.AddInterruptMoves(moves)
                break
        else:
            player.fate_discard.append(card)

def neverland_map(player, game_state):
    player.board[3].locked = False