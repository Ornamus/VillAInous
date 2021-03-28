from monte import GameState, PlayGame
from agents import Agent, ISMCTSAgent
import random
from copy import copy, deepcopy

class UnoState(GameState):
    
    MOVE_ZONE_PHASE = 0
    ACTION_PHASE = 1
    
    def __init__(self, numberOfPlayers, game_init=True, starting_player=0):
        """ Initialise the game state. n is the number of players (from 2 to 7).
        """
        self.turn = 1
        self.gameRound = 0
        self.numberOfPlayers = numberOfPlayers
        self.playerToMove = starting_player
        self.turnDirection = 1
        self.scores = [0] * self.numberOfPlayers        
        self.deck = []
        self.discard = []
        
        if game_init:          
            self.SetupRound()

    def SetupRound(self):
        self.gameRound += 1
        self.turnDirection = 1
        #self.playerToMove = 0
        self.hands = []
        self.deck = []
        self.discard = []

        for i in range(0, 4):
            self.deck.append(Card(CardColor.WILD, CardValue.WILD))
            self.deck.append(Card(CardColor.WILD, CardValue.WILD_DRAW_4))

        for color in range(0, 4):
            
            # One '0' card
            self.deck.append(Card(color, 0))
            
            for i in range(0, 2):
                
                for n in range(1, 10):
                    self.deck.append(Card(color, n))                       
                
                self.deck.append(Card(color, CardValue.SKIP))
                self.deck.append(Card(color, CardValue.REVERSE))
                self.deck.append(Card(color, CardValue.DRAW_2))
        
        #print(f"Generated deck. {len(self.deck)}")
        random.shuffle(self.deck)
        
        for player in range(0, self.numberOfPlayers):
            self.hands.append([])
            for i in range(0, 7):
                self.hands[player].append(self.deck[0])
                self.deck.remove(self.deck[0])
            #print(f"player {player} hand length: {len(self.hands[player])}")
                
        self.discard.append(self.deck[0])
        while self.discard[0].color == CardColor.WILD:
            self.discard.clear()
            random.shuffle(self.deck)
            self.discard.append(self.deck[0])
        self.deck.remove(self.discard[0])
        
        self.StartTurn()

    def Clone(self):
        """ Create a deep clone of this game state.
        """
        st = UnoState(self.numberOfPlayers, game_init=False)
        st.turn = self.turn
        st.gameRound = self.gameRound
        st.turnDirection = self.turnDirection
        st.scores = copy(self.scores)
        st.hands = deepcopy(self.hands)
        st.deck = deepcopy(self.deck)
        st.discard = deepcopy(self.discard)

        return st
    
    def CloneAndRandomize(self, observer):
        """ Create a deep clone of this game state, randomizing any information not visible to the specified observer player.
        """
        st = self.Clone()             
        #print(f"Randomizing from {observer}'s perspective")
        # The observer can see their own hand and the discard pile
        unseenCards = self.deck
        for player in range(0, self.numberOfPlayers):
            if player != observer:
                unseenCards.extend(self.hands[player])
        
        #print(f"deck length before shuffle: {len(self.deck)}")
        random.shuffle(unseenCards)
        for player in range(0, self.numberOfPlayers):
            if player != observer:
                numCards = len(self.hands[player])
                self.hands[player] = unseenCards[:numCards]
                unseenCards = unseenCards[numCards:]
        
        self.deck = unseenCards
        
        #print(f"deck length after shuffle: {len(self.deck)}")       
        return st
    
    def GetNextPlayer(self, p):
        """ Return the player to the left of the specified player """
        next = p + self.turnDirection
        if next == self.numberOfPlayers:
            next = 0
        if next < 0:
            next = self.numberOfPlayers - 1
        return next        

    def DrawCard(self):
        if len(self.deck) == 0:
            top_card = self.discard[-1]
            self.discard.remove(top_card)
            self.deck = self.discard
            random.shuffle(self.deck)
            self.discard = [top_card]
        drawn_card = self.deck[0]
        self.deck.remove(drawn_card)
        return drawn_card
    
    def StartTurn(self):          
        has_moves = False
        top_card = self.discard[-1]
        for card in self.hands[self.playerToMove]:
            if card.color == top_card.color or card.value == top_card.value or card.color == CardColor.WILD:
                has_moves = True
                break
        if not has_moves:     
            #print(f"Player {self.playerToMove}: No moves, drawing a card")
            drawn_card = self.DrawCard()
            if drawn_card.color == top_card.color or drawn_card.value == top_card.value or drawn_card.color == CardColor.WILD:
                if drawn_card.color != CardColor.WILD:
                    
                    self.discard.append(drawn_card)
                    # No choices here, go ahead and move on to next player
                    self.playerToMove = self.GetNextPlayer(self.playerToMove)       
                    self.StartTurn()
                else:    
                    #print("THERE'S A WILD")
                    self.hands[self.playerToMove].append(drawn_card)
            else:
                self.hands[self.playerToMove].append(drawn_card)
                # No choices here, go ahead and move on to next player
                self.playerToMove = self.GetNextPlayer(self.playerToMove)       
                self.StartTurn()
    
    def DoMove(self, move):
        """ Update a state by carrying out the given move.
            Must update playerToMove.
        """
        skip_next = False
        draw_penalty = 0
        if type(move) is Card:
            self.discard.append(move)
            self.hands[self.playerToMove].remove(move)

            if move.value == CardValue.SKIP:
                skip_next = True
            if move.value == CardValue.REVERSE:
                self.turnDirection *= -1
                if self.numberOfPlayers == 2:
                    skip_next = True
            if move.value == CardValue.DRAW_2 or move.value == CardValue.WILD_DRAW_4:
                draw_penalty = 4 if move.value == CardValue.WILD_DRAW_4 else 2
                skip_next = True
            
        self.turn += 1
        if len(self.hands[self.playerToMove]) == 0:            
            for player in range(0, self.numberOfPlayers):
                if player != self.playerToMove:
                    for card in self.hands[player]:
                        self.scores[self.playerToMove] = self.scores[self.playerToMove] + card.score
            #print(f"Round over. Hand winner: Player {self.playerToMove}. Score: {self.scores[self.playerToMove]}")
            self.SetupRound()
        else:                  
            self.playerToMove = self.GetNextPlayer(self.playerToMove) 
            for i in range(0, draw_penalty):
                self.hands[self.playerToMove].append(self.DrawCard())
            if skip_next:
                #print(f"{self.playerToMove} skipped")
                self.playerToMove = self.GetNextPlayer(self.playerToMove)    

            self.StartTurn()          
             
        return self

    
    def GetMoves(self):
        """ Get all possible moves from this state.
        """
        moves = []
        # Return empty moves if the game is over
        for player in range(0, self.numberOfPlayers):
            if self.GetResult(player) == 1:
            #if self.scores[player] >= 500:
                #print("Someone has won, exiting GetMoves()") 
                return []
        
        top_card = self.discard[-1]
        for card in self.hands[self.playerToMove]:
            if card.color == top_card.color or card.value == top_card.value or card.color == CardColor.WILD:
                if card.color == CardColor.WILD:
                    for i in range(0, 4):
                        moves.append(Card(i, card.value))
                else:
                    moves.append(card)
        
        if len(moves) == 0:
            print("GetMoves() finished mid-game without finding any moves!!!")
        
        return moves
       
    def GetResult(self, player):
        """ Get the game result from the viewpoint of player. 
        """
        return 1 if self.scores[player] >= 1 else 0

    
    def __str__(self):
        result = f"Round {self.gameRound} | Player {self.playerToMove}'s Turn | Top Card: {self.discard[-1]} \n"
        for i in range(0, self.numberOfPlayers):
            result += f"Player {i}: {len(self.hands[i])} cards, score: {self.scores[i]}\n"
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
                card = sorted_hands[i]
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

class CardColor:
    BLUE = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    WILD = 4
        
class CardValue:
    DRAW_2 = 11
    REVERSE = 12
    SKIP = 13
    WILD = 14
    WILD_DRAW_4 = 15

class Card:

    def __init__(self, color, value):
        self.color = color
        self.value = value
        if value <= 9:
            self.score = value
        elif value == CardValue.DRAW_2 or value == CardValue.REVERSE or value == CardValue.SKIP:
            self.score = 20
        elif value == CardValue.WILD or value == CardValue.WILD_DRAW_4:
            self.score = 50
        else:
            self.score = -1
            print(f"Card got invalid value: '{value}'")
               
    def __str__(self):
        color = "Unknown"
        if self.color == CardColor.BLUE:
            color = "Blue"
        elif self.color == CardColor.RED:
            color = "Red"
        elif self.color == CardColor.GREEN:
            color = "Green"
        elif self.color == CardColor.YELLOW:
            color = "Yellow"
        elif self.color == CardColor.WILD:
            color = "Wild"
        
        value = str(self.value)
        if self.value == CardValue.DRAW_2:
            value = "Draw 2"
        elif self.value == CardValue.REVERSE:
            value = "Reverse"
        elif self.value == CardValue.SKIP:
            value = "Skip"
        elif self.value == CardValue.WILD:
            value = "Wild"
        elif self.value == CardValue.WILD_DRAW_4:
            value = "Wild Draw 4"
        
        return f"{color} {value}"

    def __eq__(self, other):
        if type(self) is type(other):
            if self.value == CardValue.WILD and other.value == CardValue.WILD:
                return True
            elif self.value == CardValue.WILD_DRAW_4 and other.value == CardValue.WILD_DRAW_4:
                return True
            return self.color == other.color and self.value == other.value
        return False

    def __ne__(self, other):
        return not self.__eq__(other)#type(self) is not type(other) self.color != other.color or self.value != other.value

def main():    
    agents = [ISMCTSAgent(), Agent(), Agent()]

    wins = 0
    first_wins = 0
    second_wins = 0
    losses = 0
    first_losses = 0
    second_losses = 0
    total_games = 1000
    prev_start = 1
    for i in range(0, total_games):    
        game = UnoState(len(agents))
        #game.card_encoding = encode_cards(game) 
        #game.playerToMove = 0 if prev_start == 1 else 1
        prev_start = game.playerToMove                
        print(f"{game.playerToMove} starts")
        if PlayGame(agents, game) == 0:
            wins += 1
        else:
            losses += 1
        print(f"Current Record: {wins}-{losses} ({wins+losses} games)")
       
    print(f"\nFinal Record: {wins}-{losses} ({wins+losses} games)")

    return

if __name__ == "__main__":
    main()