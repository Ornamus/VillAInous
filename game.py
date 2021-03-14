from copy import copy, deepcopy
from enum import Enum
from moves import *
import random
from monte import GameState, PlayGame, KnockoutWhistState
from itertools import chain, combinations

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
        #players_copy = []
        #for player in self.players:
            #players_copy.append(deepcopy(player))
        st = VillainousState(deepcopy(self.players), game_init=False)
        st.playerToMove = self.playerToMove
        st.actions_used = deepcopy(self.actions_used)
        st.phase = self.phase
        st.turn = self.turn
        #for player in self.players:
            #player.hand = deepcopy(player.hand)
            #player.deck = deepcopy(player.deck)
            #player.deck_discard = deepcopy(player.deck_discard)
        return st
    
    def CloneAndRandomize(self, observer):
        """ Create a deep clone of this game state, randomizing any information not visible to the specified observer player.
        """
        st = self.Clone()             
        #print(f"Randomizing from {observer}'s perspective")
        # The observer can see their own hand and their discard pile, so the only unknown is how their deck is shuffled  
        random.shuffle(st.players[observer].deck)
        
        for player in st.players:
            if player != st.players[observer]:
                #print(f"Shuffling data for {player.identifier}")
                changeHands = True
                if changeHands:
                    unseenCards = deepcopy(player.deck) + deepcopy(player.hand)
                    random.shuffle(unseenCards)
                    numCards = len(player.hand)
                    # The first numCards unseen cards are the new hand
                    player.hand = deepcopy(unseenCards[:numCards])
                    # The rest are the new deck
                    player.deck = deepcopy(unseenCards[numCards:])      
                else:
                    unseenCards = player.deck
                    random.shuffle(unseenCards)
                    player.deck = unseenCards
        
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
    
    def EndPlayerTurn(self):
        player = self.players[self.playerToMove]
        player.first_turn = False
        while len(player.hand) < 4:
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
            if player.has_won():
                return moves
        
        player = self.players[self.playerToMove]
        if self.phase == self.MOVE_ZONE_PHASE:
            for zone in player.available_zones():
                moves.append(MoveZoneMove(zone))
          
        elif self.phase == self.ACTION_PHASE:
            actions_remaining = []
            for action in player.board_position.available_actions():
                if action not in self.actions_used:
                    actions_remaining.append(action)
            for action in actions_remaining:            
                if type(action) is PlayCardAction:
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
                elif type(action) is DiscardAction:   
                    # Get every possible combination of cards to discard
                    for cards in powerset(player.hand):
                        if len(cards) > 0:
                            moves.append(DiscardCardsMove(cards, action))
                elif type(action) is PowerAction:
                    continue
                else:
                    pass #moves.append(Move(action))
            if len(moves) > 0 or player.first_turn:
                moves.append(EndTurnMove())
        return moves
    
    def GetResult(self, player):
        """ Get the game result from the viewpoint of player. 
        """
        return 1 if self.players[player].has_won() else 0
    
    def GameOver(self):
        for player in self.players:
            if player.has_won():
                return True
        return False
    
    def __str__(self):
        result = f"Turn {self.turn} | {self.players[self.playerToMove].identifier}'s Turn "
        for player in self.players:
            result += f"| {player.identifier} - {player.power} power "
        return result
        
    def __repr__(self):
        """ Return a human-readable representation of the state
        """
        return str(self)
        result  = "Round %i" % self.tricksInRound
        result += " | P%i: " % self.playerToMove
        result += ",".join(str(card) for card in self.playerHands[self.playerToMove])
        result += " | Tricks: %i" % self.tricksTaken[self.playerToMove]
        result += " | Trump: %s" % self.trumpSuit
        result += " | Trick: ["
        result += ",".join(("%i:%s" % (player, card)) for (player, card) in self.currentTrick)
        result += "]"
        return result

class GameState:

    def __init__(self):
        self.players = []
        self.turn = 0
    
    def simulate_round(self):
        new_state = self.duplicate()
        new_state.turn += 1
        for player in new_state.players:
            player.take_turn(new_state)
        return new_state
    
    def simulate_round(self, allow_plans=False):
        new_state = self.duplicate()
        new_state.turn += 1
        for player in new_state.players:      
            plans = None
            if allow_plans:
                plans = player.agent.plan_whole_turn(player, new_state)
            if plans:
                player.take_turn(new_state, predetermined_actions=plans)
            else:
                player.take_turn(new_state)
        return new_state
    
    def duplicate(self):
        new_state = GameState()
        new_state.turn = self.turn
        new_state.players = deepcopy(self.players)
        for player in new_state.players:
            player.board = deepcopy(player.board)
        return new_state

def booty(p, gs):
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
    #for card in p.hand:
        #print(f"In hand: {card}")
    for card in target:
        #print(f"Sacrifice: {card}")
        p.discard_card(card)
    p.add_power(len(target) * 2)

class Agent:

    def plan_whole_turn(self, player_state, game_state):
        return None

    def take_actions(self, actions, player_state, game_state):
        action_records = []
        random.shuffle(actions)
        for action in actions:
            action_records.append(action.activate(player_state, game_state))
        return action_records

    def pick_zone(self, options, player_state, game_state):
        return options[random.randint(0, len(options) - 1)]

    def pick_ally_zone(self, ally, options, player_state, game_state):
        return options[random.randint(0, len(options) - 1)]            
        
    def pick_card(self, playable_cards, player_state, game_state):
        return playable_cards[random.randint(0, len(playable_cards) - 1)]
        
    def pick_discards(self, card_options, player_state, game_state):
        cards = copy(card_options)
        discards = []
        for i in range(0, random.randint(0, len(cards))):
            card = cards[random.randint(0, len(cards) - 1)]
            discards.append(card)
            cards.remove(card)
        return discards
    
    def pick_vanquish(self, vanquish_options, player_state, game_state):
        return vanquish_options[random.randint(0, len(vanquish_options) - 1)]
    
    def pick_move_ally(self, zones_with_allies, player, game_state):
        if len(zones_with_allies) > 1:
            zone = zones_with_allies[random.randint(0, len(zones_with_allies) - 1)]
        elif len(zones_with_allies) == 1:
            zone = zones_with_allies[0]
        else:
            return None, None, None
        
        ally = zone.allies[random.randint(0, len(zone.allies) - 1)]
        
        can_left = not zone.number == player.board[0].number
        can_right = not zone.number == player.board[-1].number          
            
        direction = 0
        if can_left and can_right:
            direction = random.randint(-1, 1)
        elif can_right:
            direction = random.randint(0, 1)
        else:
            direction = random.randint(-1, 0)
        if direction == 0:
            return None, None, None
        dest_zone = player.board[zone.number + direction]
        return ally, zone, dest_zone
        
class MonteCarloAgent(Agent):

    def plan_whole_turn(self, player_state, game_state):
        best_ai, best_ai_states = get_best_simulation(game_state, total_simulations=5, turn_depth=4)
        return best_ai.all_actions_performed[0]
   
class PlayerState:
       
    def __init__(self, identifier, villian, agent=Agent()):
        print(f"Player init: {identifier}")
        board_array = [
            [[], [PowerAction(1), FateAction(), MoveAllyAction()]],
            [[], [PowerAction(2), FateAction(), PlayCardAction()]],
            [[], [PowerAction(3), FateAction(), DiscardAction()]],
            [[], [PowerAction(4), FateAction(), DiscardAction()]],
            #[[MoveAllyAction(), PlayCardAction()], [PowerAction(1), FateAction()]],
            #[[PowerAction(2), MoveAllyAction()], [PlayCardAction(), DiscardAction()]],
            #[[DiscardAction(), PlayCardAction()], [PowerAction(3), PlayCardAction()]],
            #[[PowerAction(1), FateAction()], [VanquishAction(), PlayCardAction()]],
        ]
        self.identifier = identifier
        self.hand = []
        self.deck = []
        self.deck_discard = []
        self.fate = []
        self.fate_discard = []
        
        self.power = 0
        self.board_position = None
        self.board = []
        
        self.villian = villian
        self.agent = agent
        
        self.all_turn_records = []
        self.turn_record = []
        self.actions_performed = []
        self.all_actions_performed = []
        
        self.can_stay_on_zone = False
        self.first_turn = True
        
        self.deck = deepcopy(villian.generate_deck())
        random.shuffle(self.deck)
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

    def take_turn(self, game_state, predetermined_actions=None):
        self.actions_performed = []
        self.turn_record = []
        self.turn_record.append(f"Have {self.power} power")
        if game_state.turn > 1:
            if not predetermined_actions:
                options = self.available_zones()
                self.board_position = self.agent.pick_zone(options, self, game_state)
                move_action = MovePlayerAction()
                move_action.choice = self.board_position
                self.actions_performed.append(move_action)
        else:
            self.board_position = self.board[0]
            
        #self.turn_record.append(f"Moved to zone {self.board_position.number}")    
        if self.can_stay_on_zone:
            self.can_stay_on_zone = False
        
        if predetermined_actions:
            for action in predetermined_actions:
                action.activate(self, game_state)
                self.actions_performed.append(action)
        else:
            action_list = self.board_position.available_actions()            
            action_list_result = self.agent.take_actions(action_list, self, game_state)
            for action in action_list_result:
                self.actions_performed.append(action)
        
        while len(self.hand) < 4:
            self.draw_card()
        
        self.all_turn_records.append(self.turn_record)
        self.all_actions_performed.append(self.actions_performed)
    
    def available_zones(self):
        positions = []
        for zone in self.board:
            if (zone.number != self.board_position.number or self.can_stay_on_zone) and not zone.locked:
                positions.append(zone)
        return positions
    
    def get_state_score(self):
        return self.villian.get_score(self)
    
    def has_won(self):
        return self.villian.has_won(self)
    
    def draw_card(self):
        if len(self.deck) == 0:
            #print(f"Reshuffling deck. Discard size: {len(self.deck_discard)}")
            self.deck = copy(self.deck_discard)           
            #random.shuffle(self.deck)
            self.deck_discard.clear()           
        
        card = self.deck[0]
        self.hand.append(card)
        self.deck.remove(card)

    def play_card(self, game_state, choice=-1):
        zone = None
        playable_cards = []
        for card in self.hand:
            if card.cost <= self.power:
                playable_cards.append(card)
        if len(playable_cards) == 0:
            return None, None
        if choice is not -1:
            if choice[0] is None:
                return None, None
            for playable in playable_cards:
                if playable.name == choice[0].name:
                    card = playable
                    break
            if choice[1] is not None:
                zone = self.board[choice[1].number]
        else:
            card = self.agent.pick_card(playable_cards, self, game_state)
 
        if card is None:
            return None, None
        if card not in playable_cards:
            print("play_card wound up with a card that is not playable")
            return None, None
        if card.card_type is CardType.EFFECT or card.card_type is CardType.CONDITION:
            self.deck_discard.append(card)
        self.hand.remove(card)
        self.power -= card.cost
        self.turn_record.append(f"Playing {card.name}")
        zone = card.play(self, game_state, zone=zone)
        return card, zone

    def discard_card(self, card):
        self.deck_discard.append(card)
        self.hand.remove(card)
        #self.turn_record.append(f"Discarded {card.name}")

    def discard_action(self, game_state, choice=-1):
        if choice is not -1:
            if choice is [] or choice is None:
                return None
            discards = []
            for discarded_card in choice:
                for card in self.hand:
                    if card.name == discarded_card.name and card not in discards:
                        discards.append(card)
        else:
            discards = self.agent.pick_discards(self.hand, self, game_state)
        for card in discards:
            self.discard_card(card)
        return discards
    
    def play_ally_card(self, card_ally, game_state, zone=None):
        if zone is None:
            zones = []
            for potential_zone in self.board:
                if not potential_zone.locked: # TODO: is this correct
                    zones.append(zone)

            zone = self.agent.pick_ally_zone(card_ally, self.board, self, game_state)        
        zone.allies.append(card_ally)
        self.turn_record.append(f"{card_ally.name} played to zone {zone.number}")
        return zone
    
    def vanquish_action(self, game_state, choice=-1):
        if choice != -1:
            if choice is None:
                return None
            zone = self.board[choice[0].number]
            for hero_option in zone.heroes:
                if hero_option.name == choice[1].name and len(hero_option.card_ally.items) == len(choice[1].card_ally.items): # todo: item matching
                    hero = hero_option
                    break
            allies = []
            for ally in choice[2]:
                for ally_option in zone.allies:
                    if ally_option.name == ally.name and len(ally_option.card_ally.items) == len(ally.card_ally.items) and ally not in allies: # todo: item matching
                        allies.add(ally)
                        
            vanquish = (zone, hero, allies)
        else:
            defeatable = []
            for zone in self.board:
                if len(zone.allies) > 0 and len(zone.heroes) > 0:
                    allies_copy = copy(zone.allies)
                    random.shuffle(allies_copy)
                    for hero in zone.heroes:
                        allies_needed = []
                        for ally in allies_copy:
                            allies_needed.append(ally)
                            strength_sum = 0
                            for ally in allies_needed:
                                strength_sum += ally.card_ally.get_total_strength(zone)
                            if strength_sum >= hero.card_ally.get_total_strength(zone):
                                defeatable.append((zone, hero, allies_needed))
                                break
            if len(defeatable) == 0:
                return None

            vanquish = self.agent.pick_vanquish(defeatable, self, game_state)
            
        vanquish[0].heroes.remove(vanquish[1])
        self.fate_discard.append(vanquish[1])
        for ally in vanquish[2]:
            vanquish[0].allies.remove(ally)
            self.deck_discard.append(ally)
        return vanquish
        
    def add_power(self, power):
        self.power += power

    def print_state(self):
        pass#print(f"Player {self.identifier}: {self.power} power, hand: {len(self.hand)}")
        
    def __eq__(self, other):
        return self.identifier == other.identifier and self.power == other.power
    
    def __ne__(self, other):
        return self.identifier != other.identifier or self.power != other.power

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
        if len(self.heroes) > 0:
            return copy(self.actions)
        return copy(self.actions) + copy(self.actions_blockable)
    
    def __eq__(self, other):
        if self is None and other is None:
            return True
        if self is None or other is None:
            return False
        return self.number == other.number and self.name == other.name

    def __ne_(self, other):
        return self.number != other.number or self.name != other.name       

class CardType:
    EFFECT = 1
    ALLY = 2
    ITEM = 3
    CONDITION = 4
    CURSE = 5
        
class Card:
    
    def __init__(self, cost, name, card_type):
        self.name = name
        self.cost = cost
        self.card_type = card_type
        self.code = None
        self.card_ally = None
        self.targeted = False
        self.target_set = lambda: []
        
    def play(self, player, game_state, target=None, zone=None):
        if self.card_type == CardType.EFFECT:
            if self.code is not None:
                if self.targeted:
                    self.code(target, player, game_state)
                else:
                    self.code(player, game_state)
        elif not self.card_type == CardType.CONDITION:
            return player.play_ally_card(self, game_state, zone=zone)
        elif self.card_type == CardType.CONDITION:
            pass
        else:
            print(f"ERROR: Don't know what to do with card. Name={self.name}, type={self.card_type}")
        return None

    def __str__(self):
        return f"{self.name} ({self.cost})"
        
    def __eq__(self, other):
        return self.name == other.name and self.cost == other.cost and self.card_type == other.card_type

    def __ne__(self, other):
        return self.name != other.name or self.cost != other.cost or self.card_type != other.card_type

    def __hash__(self):
        return hash((self.name, self.cost, self.card_type))

class CharacterType:
    ALLY = 1
    HERO = 2

class Character:
     
    def __init__(self, strength, character_type):
        self.card_ally_type = character_type
        self.strength = strength      
        self.items = []
    
    def get_total_strength(self, zone):
        for item in self.items:
            pass
        return self.strength

class Action:

    def __init__(self):
        self.choice = -1
    
    def activate(self, player, game_state):
        pass

    def __str__(self):
        if self.choice:
            return f"{type(self)} - {self.choice}"
        else:
            return f"{type(self)}"

    def __eq__(self, other):
        return type(self) is type(other)
        
    def __ne__(self, other):
        return type(self) is not type(other)

class MovePlayerAction(Action):

    def activate(self, player, game_state):
        if self.choice:
            player.board_position = self.choice
        else:
            print("MovePlayerAction activated with None choice, warning!")

    def  __str__(self):
        return f"Move Player to zone {self.choice.number}"        

class PowerAction(Action):

    def __init__(self, power):
        super().__init__()
        self.power = power

    def activate(self, player, game_state):
        player.turn_record.append(f"Gained {self.power} power")
        player.power += self.power
        return self

    def  __str__(self):
        return f"Gained {self.power} power"

    def __eq__(self, other):
        return type(self) is type(other) and self.power == other.power
        
    def __ne__(self, other):
        return type(self) is not type(other) or self.power != other.power
       
class PlayCardAction(Action):

    def activate(self, player, game_state):
        if len(player.hand) == 0:
            return self
        record = copy(self)
        card, zone = player.play_card(game_state, choice=self.choice)
        record = copy(self)
        record.choice = (card, zone)
        return record
    
    def  __str__(self):
        if self.choice != -1:
            if self.choice[1]:
                return f"Play Card: {self.choice[0]} to zone {self.choice[1].number}"
            else:
                return f"Play Card: {self.choice[0]}"
        else:
            return "Skipped Play Card"

class DiscardAction(Action):

    def activate(self, player, game_state):
        if len(player.hand) == 0:
            return self      
        record = copy(self)
        record.choice = player.discard_action(game_state, choice=self.choice)
        return record

    def  __str__(self):
        if self.choice:
            return f"Discarded {len(self.choice)} cards"
        else:
            return "Discarded no cards"

class VanquishAction(Action):
    
    def activate(self, player, game_state):
        record = copy(self)
        record.choice = player.vanquish_action(game_state, choice=self.choice)
        return record
        
    def  __str__(self):
        if self.choice:
            return f"Vanquished {self.choice[1]}?"
        else:
            return "Skipped vanquish"
           
class FateAction(Action):

    def activate(self, player, game_state):
        player.turn_record.append(f"Fated")   
        return self

    def  __str__(self):
        return "Fated"        
    
class MoveAllyAction(Action):

    def activate(self, player, game_state):
        zones_with_allies = []
        for zone in player.board:
            if len(zone.allies) > 0: # or len(zone.items) > 0
                zones_with_allies.append(zone)
        if len(zones_with_allies) == 0:
            return self
            
        if self.choice != -1:
            #if self.choice[0] is None or self.choice[1] is None or self.choice[2] is None:
                #return self
            ally = None
            zone = player.board[self.choice[1].number]
            for ally_option in zone.allies:
                print(ally_option.name)
                if ally_option.card_ally is None:
                    print(f"[WARNING] {ally_option.name} has no card_ally")
                if ally_option.name == self.choice[0].name and len(ally_option.card_ally.items) == len(self.choice[0].card_ally.items):
                    ally = ally_option
                    break
            dest_zone = player.board[self.choice[2].number]
            if ally == None:
                print("Ally was not set when it should've been")
                return self
        else:
            ally, zone, dest_zone = player.agent.pick_move_ally(zones_with_allies, player, game_state)
            if not zone or not ally or not dest_zone:
                return self
        zone.allies.remove(ally)
        dest_zone.allies.append(ally)
        player.turn_record.append(f"Move {ally.name} zone: {zone.number} -> {dest_zone.number}")
        
        record = copy(self)
        record.choice = (ally, zone, dest_zone)
        return record

    def  __str__(self):
        if self.choice != -1:
            ally = self.choice[0]
            zone = self.choice[1]
            dest = self.choice[2]
            return f"Move Ally {ally}: Zone {zone.number} -> zone {dest.number}"
        else:
            return "Skipped Move Ally"

class Villian:

    def generate_deck(self):
        deck = []
        for i in range(30):
            card = None
            if i < 10:
                card = Card(1, "Booty", CardType.EFFECT)
                card.code = booty
            elif i < 20:
                card = Card(3, "Sacrifices", CardType.EFFECT)
                card.code = sacrifice
                card.targeted = True
                card.target_set = sacrifice_targets
            elif i < 30:
                card = Card(1, "An Ally", CardType.ALLY)
                card.card_ally = Character(3, CharacterType.ALLY)
            if card:
                deck.append(card)
        return deck
    
    def get_score(self, player_state):
        return player_state.power

    def has_won(self, player_state):
        return player_state.power >= 25


def get_best_simulation(starting_state, total_simulations=500, turn_depth=5):
    best_ai = None
    best_ai_states = None
    best_ai_simulation_number = -1   
    
    starting_state = starting_state.duplicate()
    for player in starting_state.players:
        player.all_actions_performed = []
    #random.seed(2)
                
    ai_wins = 0
    opponent_wins = 0
    for simulation_number in range(1, total_simulations + 1):        
        current_state = starting_state.duplicate()
        states = [current_state]
        for i in range(turn_depth):
            current_state = current_state.simulate_round()
            states.append(current_state)
            current_state.players[0].print_state()
            if current_state.players[0].has_won() or current_state.players[1].has_won():
                if current_state.players[0].has_won():
                    ai_wins += 1
                elif current_state.players[1].has_won():
                    opponent_wins += 1
                break
        ai_result = current_state.players[0]    
        print(f"Sim #{simulation_number} AI score: {ai_result.get_state_score()}. Won? {ai_result.has_won()}. Turns: {len(states)}.")
        if best_ai is None:
            best_ai = ai_result
            best_ai_states = states
            best_ai_simulation_number = simulation_number
        else:
            if best_ai.has_won() and not ai_result.has_won():
                continue
                
            if ai_result.has_won() and not best_ai.has_won(): # Won when the best AI didn't
                best_ai = ai_result
                best_ai_states = states
                best_ai_simulation_number = simulation_number
            elif ai_result.has_won() and len(states) < len(best_ai_states): # Won in less turns
                best_ai = ai_result
                best_ai_states = states
                best_ai_simulation_number = simulation_number
            elif ai_result.get_state_score() > best_ai.get_state_score(): # Ends in a more favorable position
                best_ai = ai_result
                best_ai_states = states
                best_ai_simulation_number = simulation_number
    print("=====================")
    completed_games = opponent_wins + ai_wins
    #print(f"======\nAI winrate: {(ai_wins/completed_games)*100:.2f}% out of {completed_games} games")    
    print(f"BEST AI: #{best_ai_simulation_number}. Score: {best_ai.get_state_score()}. Won? {best_ai.has_won()}. Turns: {len(best_ai_states)}.")
    
    return best_ai, best_ai_states

def main():
    # print("Villainous :)")
    
    players = []
    for i in range(0, 2):
        players.append(PlayerState("AI" if i == 0 else f"Opponent {i}", Villian()))
    PlayGame(VillainousState(players))
    #PlayGame(KnockoutWhistState(2))
    return
    
    random.seed(2)
    starting_state = GameState()
    ai = PlayerState("AI", maleficent.MaleficentVillian(), agent=MonteCarloAgent()) #Villian())
    starting_state.players.append(ai)
    
    opponent = PlayerState("Opponent", Villian())
    starting_state.players.append(opponent)
    
    current_state = starting_state.duplicate()  
    for i in range(5000):
        print(f"Turn: {current_state.turn}")
        current_state = current_state.simulate_round(allow_plans=True)
        if current_state.players[0].has_won() or current_state.players[1].has_won():
            print(" A VICTORY HAS OCCURRED ")
            break
    
    index = 0
    for turn in current_state.players[0].all_actions_performed:
        print(f"========= Turn {index + 1} ==========")
        for action in turn:
            print(str(action))
        index += 1
        
    return
    
    TOTAL_SIMULATIONS = 25
    TURN_DEPTH = 200
    
    random.seed(2)
    best_ai, best_ai_states = get_best_simulation(starting_state, total_simulations=TOTAL_SIMULATIONS, turn_depth=TURN_DEPTH)
    
    print("Starting hand:")
    for card in best_ai_states[0].players[0].hand:
        print(str(card))   
    index = 0
    for turn in best_ai.all_actions_performed:
        print(f"========= Turn {index + 1} ==========")
        for action in turn:
            print(str(action))
        index += 1

    print("\nTrying to apply to real game:")
    
    current_state = starting_state.duplicate()    
    for turn in best_ai.all_actions_performed:
        current_state = current_state.play_round("AI", turn)      
    
    index = 0
    for turn in current_state.players[0].all_actions_performed:
        print(f"========= Turn {index + 1} ==========")
        for action in turn:
            print(str(action))
        index += 1
    
    

    
if __name__ == "__main__":
    main()