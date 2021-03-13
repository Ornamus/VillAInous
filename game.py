from copy import copy, deepcopy
from enum import Enum
import random
import maleficent

VERBOSE_LOG = False

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

def sacrifice(p, gs):
    amount = p.discard_action(gs)
    p.add_power(len(amount) * 2)

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
            [[MoveAllyAction(), PlayCardAction()], [PowerAction(1), FateAction()]],
            [[PowerAction(2), MoveAllyAction()], [PlayCardAction(), DiscardAction()]],
            [[DiscardAction(), PlayCardAction()], [PowerAction(3), PlayCardAction()]],
            [[PowerAction(1), FateAction()], [VanquishAction(), PlayCardAction()]],
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
                options = self.available_positions()
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
    
    def available_positions(self):
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
        self.turn_record.append(f"Discarded {card.name}")

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
        
    def play(self, player, game_state, zone=None):
        if self.card_type == CardType.EFFECT:
            if self.code is not None:
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

class MovePlayerAction(Action):

    def activate(self, player, game_state):
        if self.choice:
            player.board_position = self.choice
        else:
            print("MovePlayerAction activated with None choice, warning!")

    def  __str__(self):
        return f"Move Player to zone {self.choice.number}"

class PowerAction(Action):
    
    power = 1

    def __init__(self, power):
        super().__init__()
        self.power = power

    def activate(self, player, game_state):
        player.turn_record.append(f"Gained {self.power} power")
        player.power += self.power
        return self

    def  __str__(self):
        return f"Gained {self.power} power"

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