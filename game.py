from copy import copy, deepcopy
from enum import Enum
from moves import *
import random
import collections
from monte import GameState, PlayGame, ISMCTS
from itertools import chain, combinations
import hook
import operator
import numpy as np

VERBOSE_LOG = False

def powerset(iterable):
    """
    powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)
    """
    xs = list(iterable)
    # note we return an iterator rather than a list
    return chain.from_iterable(combinations(xs,n) for n in range(len(xs)+1))

class VillainousState(GameState):
    
    MOVE_ZONE_PHASE = 0
    ACTION_PHASE = 1
    
    def __init__(self, players, game_init=True):
        """ Initialise the game state. n is the number of players (from 2 to 7).
        """
        self.numberOfPlayers = len(players)
        self.playerToMove = 0            
        self.players = players
        self.actions_used = []
        self.interrupt_moves = []
        self.phase = self.ACTION_PHASE if game_init else self.MOVE_ZONE_PHASE
        self.turn = 1
        if game_init:
            for i in range(0, self.numberOfPlayers):
                player = self.players[i]
                player.first_turn = True
                extra_power = 0
                if i == 1:
                    extra_power = 1
                elif i == 2 or i == 3:
                    extra_power = 2
                elif i >= 4:
                    extra_power = 3
                player.power += extra_power
                
                for action in [a for a in player.board_position.available_actions() if type(a) is PowerAction]:
                    player.power += action.power
    
    def Clone(self):
        """ Create a deep clone of this game state.
        """
        st = VillainousState(deepcopy(self.players), game_init=False)
        st.card_encoding = self.card_encoding
        st.playerToMove = self.playerToMove
        st.actions_used = deepcopy(self.actions_used)
        st.interrupt_moves = deepcopy(self.interrupt_moves)
        st.phase = self.phase
        st.turn = self.turn

        return st
    
    def CloneAndRandomize(self, observer):
        """ Create a deep clone of this game state, randomizing any information not visible to the specified observer player.
        """
        st = self.Clone()             
        #print(f"Randomizing from {observer}'s perspective")
        # The observer can see their own hand and their discard pile, so the only unknown is how their deck is shuffled  
        random.shuffle(st.players[observer].deck)
        random.shuffle(st.players[observer].fate)
        
        for player in st.players:
            if player != st.players[observer]:
                #print(f"Shuffling data for {player.identifier}")
                unseenCards = player.deck + player.hand#deepcopy(player.deck) + deepcopy(player.hand)
                random.shuffle(unseenCards)
                numCards = len(player.hand)
                # The first numCards unseen cards are the new hand
                player.hand = unseenCards[:numCards] #deepcopy(unseenCards[:numCards])
                # The rest are the new deck
                player.deck = unseenCards[numCards:] #deepcopy(unseenCards[numCards:])   
                random.shuffle(player.fate)

        
        return st
    
    def GetNextPlayer(self, p):
        """ Return the player to the left of the specified player """
        next = p + 1
        if next == self.numberOfPlayers:
            next = 0
        return next        
    
    def DoMove(self, move):
        """ Update a state by carrying out the given move.
            Must update playerToMove.
        """
        
        #print(f"Turn {self.turn}, Doing move: {move}")
        player = self.players[self.playerToMove]
        move.perform(self, player)
        if move.parent_action is not None:
            self.actions_used.append(move.parent_action)
        if move in self.interrupt_moves:
            self.interrupt_moves.clear()
        
        did_move_phase = False
        if self.phase == self.MOVE_ZONE_PHASE:  
            if type(move) is MoveZoneMove:
                player.can_stay_on_zone = False
                for action in [a for a in player.board_position.available_actions() if type(a) is PowerAction]:
                    player.power += action.power
                    self.actions_used.append(action)
                self.phase = self.ACTION_PHASE     
                if self.GetMoves() == []:
                    self.EndPlayerTurn()
        elif self.phase == self.ACTION_PHASE:
            if self.GetMoves() == [] or type(move) is EndTurnMove:
                # Out of moves, this player's turn is over
                self.EndPlayerTurn()
        
        return self
    
    def EndPlayerTurn(self):
        player = self.players[self.playerToMove]
        player.first_turn = False
        for i in range(0, 4 - len(player.hand)): #while len(player.hand) < 4:        
            player.draw_card()
        self.playerToMove = self.GetNextPlayer(self.playerToMove)
        if self.players[self.playerToMove].first_turn:
            self.phase = self.ACTION_PHASE
        else:
            self.phase = self.MOVE_ZONE_PHASE
        self.actions_used = []
        self.turn += 1
    
    
    def GetMoves(self):
        """ Get all possible moves from this state.
        """
        moves = []
        # Return empty moves if the game is over
        for player in self.players:
            if player.has_won(self):
                return moves
        
        if len(self.interrupt_moves) > 0:
            return self.interrupt_moves
        
        player = self.players[self.playerToMove]
        if self.phase == self.MOVE_ZONE_PHASE:
            for zone in player.available_zones():
                moves.append(MoveZoneMove(zone))
          
        elif self.phase == self.ACTION_PHASE:
            actions_remaining = [action for action in player.board_position.available_actions() if action not in self.actions_used]
            #for action in player.board_position.available_actions():
                #if action not in self.actions_used:
                    #actions_remaining.append(action)
            calculated_playable_cards = False
            for action in actions_remaining:            
                if type(action) is PlayCardAction and not calculated_playable_cards: #TODO: maybe not a needed optimization
                    calculated_playable_cards = True
                    for card in player.hand:
                        if card.cost <= player.power:
                            if card.targeted:
                                targets = card.target_set(player, self)
                                for target in targets:
                                    if card.card_type == CardType.EFFECT:
                                        moves.append(PlayCardMove(card, action, target=target))
                            else:                               
                                if card.card_type == CardType.EFFECT:
                                    moves.append(PlayCardMove(card, action))
                                elif card.card_type != CardType.CONDITION:
                                    # Get every open zone to play an Ally or Item to
                                    zones = [zone for zone in player.board if (not zone.locked or card.fate)]
                                    for zone in zones:
                                        if card.card_type == CardType.ITEM and card.equip:
                                            for ally in zone.heroes if card.fate else zone.allies:
                                                moves.append(PlayCardMove(card, action, target=ally, zone=zone))
                                        else:
                                            moves.append(PlayCardMove(card, action, zone=zone))
                                        
                elif type(action) is DiscardAction:   
                    # Get every possible combination of cards to discard
                    for cards in powerset(player.hand):
                        if len(cards) > 0:
                            moves.append(DiscardCardsMove(cards, action))
                elif type(action) is MoveAllyAction or type(action) is MoveHeroAction:
                    for zone in player.board:
                        if zone.locked:
                            continue
                            
                        for entity in (zone.allies + zone.items) if type(action) is MoveAllyAction else zone.heroes:
                            if zone.number > 0 and not player.board[zone.number - 1].locked:
                                moves.append(MoveAllyMove(entity, zone, player.board[zone.number - 1], action))
                            if zone.number < 3 and not player.board[zone.number + 1].locked:
                                moves.append(MoveAllyMove(entity, zone, player.board[zone.number + 1], action))
                                                                  
                elif type(action) is VanquishAction:
                    for zone in player.board:
                        if zone.locked:
                            continue
                        for hero in zone.heroes:
                            valid_allies = zone.allies
                            
                            # TODO: need a way of tracking where these allies come from in the Move so that we can remove them properly
                            #if zone.number > 0 and not player.board[zone.number - 1].locked:
                            #    valid_allies.extend([ally for ally in player.board[zone.number - 1].allies if ally.card_ally.adjacent_vanquish])
                            #if zone.number < 3 and not player.board[zone.number + 1].locked:
                            #    valid_allies.extend([ally for ally in player.board[zone.number + 1].allies if ally.card_ally.adjacent_vanquish])
                            
                            for ally_set in powerset(valid_allies):
                                total_strength = 0
                                for ally in ally_set:
                                    total_strength += ally.get_total_strength(zone)
                                if total_strength >= hero.get_total_strength(zone):
                                    moves.append(VanquishMove(ally_set, hero, zone, action))
                
                elif type(action) is FateAction:
                    for i in range(0, self.numberOfPlayers):                   
                        if i != self.playerToMove:
                            moves.append(FateMove(i, action))
                
                elif type(action) is PowerAction:
                    continue
                else:
                    pass #moves.append(Move(action))
            if len(moves) > 0 or player.first_turn:
                moves.append(EndTurnMove())
        return moves
    
    def AddInterruptMoves(self, moves):
        self.interrupt_moves = moves
    
    def GetResult(self, player):
        """ Get the game result from the viewpoint of player. 
        """
        return 1 if self.players[player].has_won(self) else 0
    
    def __str__(self):
        result = f"Turn {self.turn} | {self.players[self.playerToMove].identifier}'s Turn " + ("\n" if self.numberOfPlayers > 1 else "")
        for player in self.players:
            heroes = 0
            allies = 0
            zone_string = ""
            for zone in player.board:
                heroes += len(zone.heroes)
                allies += len(zone.allies)
                
                hero_str = len(zone.heroes) if len(zone.heroes) > 0 else " "
                ally_str = "A" if len(zone.allies) > 0 else " "
                inside = f"{hero_str}{ally_str}"
                #inside = len(zone.heroes) if len(zone.heroes) > 0 else " "
                #inside = "A" if inside == " " and len(zone.allies) > 0 else inside
                if zone.locked:
                    zone_string += f"X{inside}X "
                elif zone.number == player.board_position.number:
                    zone_string += f"|{inside}| "
                else:
                    zone_string += f"[{inside}] "
            result += f"| {player.identifier.ljust(10)} - p={player.power:2} d={len(player.deck):2} f={len(player.fate):2} h={heroes:2} a={allies:2}   {zone_string} " + ("\n" if self.numberOfPlayers > 1 else "")
            
        return result
        
    def __repr__(self):
        """ Return a human-readable representation of the state
        """
        return str(self)

    def to_inputs(self, player_number):
        num_cards = len(self.card_encoding)# - 1
        #num_hand_cards = self.card_encoding["non_fate"]
        #print(f"Num cards: {num_cards}, non-fate: {num_hand_cards}")
        player = self.players[player_number]
        
        inputs = [1 if player_number == self.playerToMove else 0, player.power]

        for zone in player.board:
            inputs.append(1 if zone.locked else 0)
        
        sorted_hand = sorted(player.hand, key=operator.attrgetter('name'))
        sorted_discard = sorted(player.deck_discard, key=operator.attrgetter('name'))

        # One-hot encode the cards in the hand
        for i in range(0, 4):
            card_inputs = [0] * num_cards
            if i < len(sorted_hand):
                card = sorted_hand[i]
                card_inputs[self.card_encoding[card.name]] = 1           
            inputs.extend(card_inputs)
        
                
        # One-hot encode the cards in the discard pile
        for i in range(0, 30):
            card_inputs = [0] * num_cards
            if i < len(sorted_discard):
                card = sorted_discard[i]
                card_inputs[self.card_encoding[card.name]] = 1           
            inputs.extend(card_inputs)
        
        for other_player in self.players:
            if other_player != player:
                inputs.extend([1 if other_player == self.players[self.playerToMove] else 0, other_player.power])     
                for zone in other_player.board:
                    inputs.append(1 if zone.locked else 0)
                
                # One-hot encode the cards in the opponent's discard pile
                sorted_discard = sorted(other_player.deck_discard, key=operator.attrgetter('name'))
                for i in range(0, 30):
                    card_inputs = [0] * num_cards
                    if i < len(sorted_discard):
                        card = sorted_discard[i]
                        card_inputs[self.card_encoding[card.name]] = 1           
                    inputs.extend(card_inputs)
        return inputs

def gold_stash(p, gs):
    p.add_power(2)

def sacrifice_targets(p, gs):
    options = []
    skipped_sacrifices = False
    for card in p.hand:
        if card.name == "Sacrifices" and not skipped_sacrifices:
            skipped_sacrifices = True
            continue
        options.append(card)
    
    return powerset(options)

def sacrifice(target, p, gs):
    for card in target:
        p.discard_card(card)
    p.add_power(len(target) * 2)

   
class PlayerState:
       
    def __init__(self, identifier, Villain, agent=None):
        print(f"Player init: {identifier}")
        board_array = [
            #[[PowerAction(1), DiscardAction()],     [VanquishAction(), PlayCardAction()]],
            #[[PowerAction(1), PlayCardAction()],       [FateAction(), DiscardAction()]],
            #[[PlayCardAction(number=1), MoveAllyAction()],      [PowerAction(3), PlayCardAction(number=2)]],
            #[[FateAction(), PowerAction(2)], [MoveHeroAction(), PlayCardAction()]],
            [[PlayCardAction(number=1), VanquishAction()], [PowerAction(1), PlayCardAction(number=0)]],
            [[PlayCardAction(), PowerAction(2)],       [VanquishAction(), Action()]],
            [[MoveAllyAction(), Action()],      [PowerAction(2), DiscardAction()]],
            [[PowerAction(4), DiscardAction()], [MoveAllyAction(), PlayCardAction()]],
        ]
        self.identifier = identifier
        self.hand = []
        self.deck_discard = []
        self.fate_discard = []
        
        self.vanquish_history = []
        
        self.power = 0
        self.board_position = None
        self.board = []
        
        self.Villain = Villain
        self.agent = agent
        
        self.all_turn_records = []
        self.turn_record = []
        self.actions_performed = []
        self.all_actions_performed = []
        
        self.can_stay_on_zone = False
        self.first_turn = True
        
        self.deck = Villain.generate_deck() #deepcopy(Villain.generate_deck())
        random.shuffle(self.deck)
        
        self.fate = Villain.generate_fate() #deepcopy(Villain.generate_fate())
        random.shuffle(self.fate)
        
        for i in range(4):
            self.draw_card()
        for i in range(4):
            zone = BoardZone(i)
            all_actions = board_array[i]
            for action in all_actions[0]:
                zone.actions_blockable.append(action)
            for action in all_actions[1]:
                zone.actions.append(action)
            self.board.append(zone)
        self.board_position = self.board[0]
        Villain.init(self)
    
    def available_zones(self):
        positions = []
        for zone in self.board:
            if (zone.number != self.board_position.number or self.can_stay_on_zone) and not zone.locked:
                positions.append(zone)
        return positions
    
    def has_won(self, game_state):
        return self.Villain.has_won(self, game_state)
    
    def draw_card(self):
        if len(self.deck) == 0:
            #print(f"Reshuffling deck. Discard size: {len(self.deck_discard)}")
            self.deck = copy(self.deck_discard)           
            #random.shuffle(self.deck)
            self.deck_discard.clear()           
        
        card = self.deck[0]
        self.hand.append(card)
        self.deck.remove(card)

    def get_fate_card(self):
        if len(self.fate) == 0:
            #print(f"Reshuffling fate for {self.identifier}. Discard size: {len(self.fate_discard)}")
            self.fate = copy(self.fate_discard)           
            #random.shuffle(self.fate)
            self.fate_discard.clear()           
        
        card = self.fate[0]
        self.fate.remove(card)  
        return card        

    def discard_card(self, card):
        self.deck_discard.append(card)
        self.hand.remove(card)
    
    def add_power(self, power):
        self.power += power
        if self.power < 0:
            self.power =0 
        
    def __eq__(self, other):
        return self.identifier == other.identifier# and self.power == other.power
    
    def __ne__(self, other):
        return self.identifier != other.identifier# or self.power != other.power

class Agent:

    def GetMove(self, state):
        move = random.choice(state.GetMoves())
        print(f"Random Move: {move}")
        return move


class ISMCTSAgent(Agent):

    def __init__(self, iterations=500, rollout_agent=None):
        self.iterations = iterations
        self.rollout_agent = rollout_agent

    def GetMove(self, state, moves=None):
        m, node = ISMCTS(rootstate = state, itermax = self.iterations, verbose = False, rollout_agent=self.rollout_agent)
        print(f"Best Move: {m} ({(node.wins/node.visits)*100:.1f}%)\n")
        return m


class RegressionAgent(Agent):

    def __init__(self, verbose=True):
        super().__init__()
        self.estimator = None
        self.verbose = verbose
        
    def GetMove(self, state, moves=None):
        best_move = None
        best_val = 0
        
        #inputs = [state.Clone().DoMove(move).to_inputs(state.playerToMove) for move in state.GetMoves()]
        inputs = []
        move_options = []
        if not moves:
            moves = state.GetMoves()
        for move in moves:            
            future_state = state.CloneAndRandomize(state.playerToMove)
            future_state.DoMove(move)
            if len(future_state.interrupt_moves) > 0:
                best_pred = 0
                for second_move in future_state.GetMoves():
                    second_future_state = future_state.CloneAndRandomize(state.playerToMove)
                    second_future_state.DoMove(second_move)
                    inputs.append(second_future_state.to_inputs(state.playerToMove))
                    move_options.append(move)
                    
            else:
                inputs.append(future_state.to_inputs(state.playerToMove))
                move_options.append(move)                          
        
        printed_moves = []
        index = 0
        predictions = self.estimator.model(np.array(inputs), training=False)#self.estimator.predict(inputs, verbose=0)       
        if len(inputs) == 1:
            predictions = [predictions]
        for prediction in predictions:
            if prediction > best_val or best_move is None:
                best_val = prediction
                best_move = move_options[index]    
            if self.verbose:
                #print(prediction)
                print(f"[M:{move_options[index]})")# {prediction*100:.1f}%")
            index += 1            
        
        if self.verbose:
            print(f"\nBest Move: {best_move}\n")# ({best_val*100:.1f}%)\n")
        return best_move

class BoardZone:
    
    def __init__(self, number):
        self.number = number
        self.name = "Zone"
        self.actions = []
        self.actions_blockable = []
        self.locked = False
        
        self.heroes = []
        self.allies = []
        self.items = []
    
    def available_actions(self):
        if self.locked:
            return []
        item_bonus = []
        for item in self.items:
            item_bonus.extend(item.actions_granted)
        if len(self.heroes) > 0:
            return self.actions + item_bonus
        return self.actions + self.actions_blockable + item_bonus
    
    def __eq__(self, other):
        if self is None and other is None:
            return True
        if self is None or other is None:
            return False
        return self.number == other.number and self.name == other.name

    def __ne__(self, other):
        if self is None and other is None:
            return False
        if self is None or other is None:
            return True
        return self.number != other.number or self.name != other.name       

class CardType:
    EFFECT = 1
    ALLY = 2
    ITEM = 3
    CONDITION = 4
    HERO = 5    
    CURSE = 6
        
class Card:
    
    def __init__(self, cost, name, card_type):
        self.name = name
        self.cost = cost
        self.card_type = card_type
        self.code = None
        self.targeted = False
        self.target_set = lambda: []
        self.fate = False
        
        # Item Settings
        self.actions_granted = []
        self.equip = False
        self.strength_bonus = 0
        
        # Ally / Hero Settings
        self.strength = 0    
        self.items = []
        self.current_zone = -1
        self.adjacent_vanquish = False
    
    def play(self, player, game_state, target=None, zone=None):
        if self.card_type == CardType.EFFECT:
            if self.code is not None:
                if self.targeted:
                    self.code(target, player, game_state)
                else:
                    self.code(player, game_state)
        elif self.card_type == CardType.ITEM:
            if self.equip: # TODO: remove this check for target once the code on line 179ish works
                if target is None:
                    print(f"Card {self} given no target despite being an equip item")
                target.items.append(self)
            else:
                zone.items.append(self)
                if self.code is not None:
                    self.code(player, game_state)
        elif not self.card_type == CardType.CONDITION:
            if self.fate:
                zone.heroes.append(self)
            else:
                zone.allies.append(self)
        elif self.card_type == CardType.CONDITION:
            pass
        else:
            print(f"ERROR: Don't know what to do with card. Name={self.name}, type={self.card_type}")
        return None

    def get_total_strength(self, zone):
        strength = self.strength
        for item in self.items:
            strength += item.strength_bonus
        return strength

    def __str__(self):
        return f"{self.name} ({self.cost})"
        
    def __eq__(self, other):
        if self.name == other.name and self.cost == other.cost and self.card_type == other.card_type:
            if self.card_type == CardType.HERO or self.card_type == CardType.ALLY or (self.card_type == CardType.ITEM and not self.equip):
                return True#return collections.Counter(self.items) == collections.Counter(other.items)
            else:
                return True
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.name, self.cost, self.card_type))

class Action:

    def __init__(self, number=0):
        self.choice = -1
        self.number = number

    def __str__(self):
        if self.choice:
            return f"{type(self)} - {self.choice}"
        else:
            return f"{type(self)}"

    def __eq__(self, other):
        return type(self) is type(other) and self.number == other.number
        
    def __ne__(self, other):
        return type(self) is not type(other) or self.number != other.number

class MovePlayerAction(Action):

    def  __str__(self):
        return f"Move Player Action"        

class PowerAction(Action):

    def __init__(self, power, number=0):
        super().__init__(number=number)
        self.power = power

    def  __str__(self):
        return f"{self.power} Power Action"

    def __eq__(self, other):
        return super().__eq__(other) and self.power == other.power
        
    def __ne__(self, other):
        return super().__ne__(other) or self.power != other.power
       
class PlayCardAction(Action):
    
    def  __str__(self):
        return "Play Card Action"

class DiscardAction(Action):

    def  __str__(self):
        return "Discard Action"

class VanquishAction(Action):
           
    def  __str__(self):      
        return "Vanquish Action"
           
class FateAction(Action):

    def  __str__(self):
        return "Fate Action"        
    
class MoveAllyAction(Action):

    def  __str__(self):
        return "Move Ally"

class MoveHeroAction(Action):

    def __str__(self):
        return "Move Hero"
        
def unlock_the_magic(p, gs):
    if p.board[3].locked:
        p.board[3].locked = False
    else:
        p.power += 7
        for i in range(3, -1, -1):
            zone = p.board[i]
            if len(zone.heroes) > 0:
                hero = zone.heroes[0]
                zone.heroes.remove(hero)
                p.fate_discard.append(hero)
                return

class Villain:
    
    def init(self, player):
        player.board[3].locked = True
    
    def generate_deck(self):
        deck = []
        for i in range(30):
            card = None
            if i < 10:
                card = Card(1, "Gold Stash", CardType.EFFECT)
                card.code = gold_stash
            elif i < 19:
                card = Card(3, "Sacrifices", CardType.EFFECT)
                card.code = sacrifice
                card.targeted = True
                card.target_set = sacrifice_targets
            elif i <= 27:
                card = Card(0, "Gremlin", CardType.ALLY)
                card.strength = 3
            else:
                card = Card(2, "Unlock the Magic", CardType.EFFECT)
                card.code = unlock_the_magic
            if card:
                deck.append(card)
        #for i in range(1, 7):
            #card = Card(2, "Cannon", CardType.ITEM)
           # card.actions_granted.append(VanquishAction(number=-i))
            #deck.append(card)
        return deck
    
    def generate_fate(self):
        fate = []
        for i in range(20):
            if i < 10:
                card = Card(0, "Taxes", CardType.EFFECT)
                card.code = lambda p, gs: p.add_power(-3)
                card.fate = True
            elif i < 18:
                card = Card(0, "Politician", CardType.HERO)
                card.strength = 2
                card.fate = True
            else:
                card = Card(0, "Chungus", CardType.ALLY)
                card.strength = 6
                card.fate = True
            if card:
                fate.append(card)
        return fate

    def get_score(self, player_state):
        return player_state.power

    def has_won(self, player_state, game_state):
        heroes = 0
        for zone in player_state.board:
            heroes += len(zone.heroes)
        return player_state.power >= 15 and heroes <= 1

def encode_cards(state):
    unique = []
    cards = []
    for player in state.players:
        cards.extend(player.hand + player.deck_discard + player.deck + player.fate + player.fate_discard)
    for card in cards:
        if card not in unique:
            unique.append(card)
    
    unique = sorted(unique, key=operator.attrgetter('name'))
    
    encodings = {}
    num = 0
    non_fate = 0
    for card in unique:
        encodings[card.name] = num
        num += 1
        if not card.fate:
            non_fate += 1
    
    #encodings["non_fate"] = non_fate
    print(encodings)
    return encodings


def main():
    # print("Villainous :)")
    
    #agents = [ISMCTSAgent(iterations=500, rollout_agent=RegressionAgent(verbose=False)), ISMCTSAgent(iterations=500)]
    agents = [ISMCTSAgent(iterations=500), RegressionAgent()]
    #agents = [ISMCTSAgent(iterations=500), ISMCTSAgent(iterations=500)]
    #agents = [ISMCTSAgent(iterations=500), Agent()]
    #agents = [RegressionAgent(), Agent()]
    #agents = [ISMCTSAgent(iterations=500, rollout_agent=RegressionAgent(verbose=False)), ISMCTSAgent(iterations=500)]
    wins = 0
    first_wins = 0
    second_wins = 0
    losses = 0
    first_losses = 0
    second_losses = 0
    total_games = 500
    prev_start = 1
    for i in range(0, total_games):
        players = []
        for i in range(0, 2):
            player = PlayerState(f"Monte" if i == 0 else f"Reggie", Villain())
            players.append(player)
    
        game = VillainousState(players)
        game.card_encoding = encode_cards(game) 
        game.playerToMove = 0 if prev_start == 1 else 1
        prev_start = game.playerToMove                
        print(f"{game.playerToMove} starts")
        if PlayGame(agents, game) == 0:
            wins += 1
            if prev_start == 0:
                first_wins += 1
            else:
                second_wins += 1
        else:
            losses += 1
            if prev_start == 0:
                first_losses += 1
            else:
                second_losses += 1
        print(f"Current Record: {wins}-{losses} ({wins+losses} games)")
        print(f"Going First: {first_wins}-{first_losses}  ({first_wins+first_losses} games)")
        print(f"Going Second: {second_wins}-{second_losses}  ({second_wins+second_losses} games)")
    print(f"\nFinal Record: {wins}-{losses} ({wins+losses} games)")
    print(f"Going First: {first_wins}-{first_losses}  ({first_wins+first_losses} games)")
    print(f"Going Second: {second_wins}-{second_losses}  ({second_wins+second_losses} games)")
    return
    
    
    
if __name__ == "__main__":
    main()