from monte import GameState, SelfPlayGame, PlayGame, get_model
from agents import Agent, ISMCTSAgent, AlphaMCTSAgent, RegressionAgent
import random
from copy import copy, deepcopy
from itertools import groupby, chain
from multiprocessing import Pool
import numpy as np
import time

NONE = '.'
RED = 'R'
YELLOW = 'Y'

def diagonalsPos (matrix, cols, rows):
    """Get positive diagonals, going from bottom-left to top-right."""
    for di in ([(j, i - j) for j in range(cols)] for i in range(cols + rows -1)):
        yield [matrix[i][j] for i, j in di if i >= 0 and j >= 0 and i < cols and j < rows]

def diagonalsNeg (matrix, cols, rows):
    """Get negative diagonals, going from top-left to bottom-right."""
    for di in ([(j, i - cols + j + 1) for j in range(cols)] for i in range(cols + rows - 1)):
        yield [matrix[i][j] for i, j in di if i >= 0 and j >= 0 and i < cols and j < rows]

class ConnectFourState(GameState):
    
    MOVE_ZONE_PHASE = 0
    ACTION_PHASE = 1
    
    def __init__(self, game_init=True, starting_player=0):
        """ Initialise the game state."""
        self.turn = 1
        self.numberOfPlayers = 2
        self.playerToMove = starting_player
        
        self.cols = 7
        self.rows = 6
        self.win = 4
        self.board = [[NONE] * self.rows for _ in range(self.cols)]

    def Clone(self):
        """ Create a deep clone of this game state.
        """
        st = ConnectFourState(game_init=False)
        st.turn = self.turn
        st.playerToMove = self.playerToMove
        st.cols = self.cols
        st.rows = self.rows
        st.win = self.win
        
        st.board = deepcopy(self.board)

        return st
    
    def CloneAndRandomize(self, observer):
        """ Create a deep clone of this game state, randomizing any information not visible to the specified observer player.
        """
        st = self.Clone()                  
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
        self.insert(move, RED if self.playerToMove == 0 else YELLOW)          
        self.playerToMove = self.GetNextPlayer(self.playerToMove)
        return self

    
    def GetMoves(self):
        """ Get all possible moves from this state.
        """
        moves = []
        # Return empty moves if the game is over
        if self.getWinner():
            return []
        
        for col in range(self.cols):
            c = self.board[col]
            if c[0] == NONE:
                moves.append(col)        
        
        return moves
       
    def GetResult(self, player):
        """ Get the game result from the viewpoint of player. 
        """
        if player == 0:
            return 1 if self.getWinner() == RED else 0
        else:
            return 1 if self.getWinner() == YELLOW else 0

    
    def __str__(self):
        result = f"Turn {self.turn} | Player {self.playerToMove}'s Turn \n"
        result += self.getBoard()
        return result
        
    def __repr__(self):
        """ Return a human-readable representation of the state
        """
        return str(self)
    
    def to_inputs(self, player_number):
        inputs = deepcopy(self.board)
        final_inputs = []
        my_color = RED if player_number == 0 else YELLOW
        opponent_color = YELLOW if player_number == 0 else RED
        for y in range(self.rows):
            for x in range(self.cols):                 
                inputs[x][y] = 1 if inputs[x][y] == my_color else (-1 if inputs[x][y] == opponent_color else 0)
                final_inputs.append(inputs[x][y])
                continue
                final_inputs.extend([
                        1 if inputs[x][y] == 1 else 0, 
                        1 if inputs[x][y] == -1 else 0, 
                        1 if inputs[x][y] == 0 else 0
                ])

        return final_inputs
    
    def predict(self, model, player, use_boards=False):
        if use_boards:
            boards = []
            for data in np.array([self.to_inputs(player)]):
                #print("=========Loading Board========")
                board = []
                prev = 0
                row_sum = 0
                for i in range(6):
                    row = data[prev:(i+1)*7]
                    board.append(row)
                    prev = (i+1)*7
                    #print(row)
                    row_sum += len(row)
                boards.append(board)

            boards = np.asarray(boards)    
            boards = boards.reshape(len(boards), 6, 7, 1)
        else:
            boards = np.array([self.to_inputs(player)])
        prediction = model.predict(boards, verbose=0)
        #prediction = prediction[0]
        #print(prediction)
        #print(prediction[0])
        #print(prediction[1:])
        return prediction[0], prediction[1:]
    
    def insert (self, column, color):
        """Insert the color in the given column."""
        c = self.board[column]
        if c[0] != NONE:
            raise Exception('Column is full')

        i = -1
        while c[i] != NONE:
            i -= 1
        c[i] = color

    def getWinner (self):
        """Get the winner on the current board."""
        lines = (
            self.board, # columns
            zip(*self.board), # rows
            diagonalsPos(self.board, self.cols, self.rows), # positive diagonals
            diagonalsNeg(self.board, self.cols, self.rows) # negative diagonals
        )

        for line in chain(*lines):
            for color, group in groupby(line):
                if color != NONE and len(list(group)) >= self.win:
                    return color
    
    def getBoard(self):
        result = '  '.join(map(str, range(self.cols))) + "\n"
        for y in range(self.rows):
            result += '  '.join(str(self.board[x][y]) for x in range(self.cols)) + "\n"
        result += "\n"
        return result
    
    def printBoard (self):
        """Print the board."""
        print('  '.join(map(str, range(self.cols))))
        for y in range(self.rows):
            print('  '.join(str(self.board[x][y]) for x in range(self.cols)))
        print()


def PlaySomeGames(games):    
    agents = [ISMCTSAgent(iterations=500), ISMCTSAgent(iterations=500)] 
    #agents = [AlphaMCTSAgent(iterations=500, model=get_model(0, train=False)), Agent()]
    
    wins = 0
    losses = 0
    ties = 0
    prev_start = 1
    for i in range(0, games):    
        game = ConnectFourState()
        game.playerToMove = 0 if prev_start == 1 else 1
        prev_start = game.playerToMove                
        result = SelfPlayGame(agents, game)
        if result == 0:
            wins += 1
        elif result == 1:
            losses += 1
        else:
            ties += 1
        print(f"Current Record: {wins}-{losses} ({wins+losses} games)")
    return wins, losses, ties

def main():    
    agents = [AlphaMCTSAgent(iterations=500, model=get_model(1, train=True)), Agent()]
    
    wins = 0
    first_wins = 0
    second_wins = 0
    losses = 0
    first_losses = 0
    second_losses = 0
    ties = 0
    total_games = 4
    prev_start = 1
    
    sim_start = time.perf_counter()
    if False:
        with Pool(5) as p:
            results = p.map(PlaySomeGames, [min(5, total_games)] * int(total_games/(min(5, total_games))))
        sim_end = time.perf_counter()        
        for result in results:
            wins += result[0]
            losses += result[1]
            ties += result[2]
        #print(f"\nFinal Record: {wins}-{losses} ({wins+losses} games)")
        #print(f"Time taken: {sim_end - sim_start:0.4f} seconds.")
        #return
    else:
        for i in range(0, total_games):    
            game = ConnectFourState()
            game.playerToMove = 0 if prev_start == 1 else 1
            prev_start = game.playerToMove                
            print(f"{game.playerToMove} starts")
            result = SelfPlayGame(agents, game)
            if result == 0:
                wins += 1
            elif result == 1:
                losses += 1
            else:
                ties += 1
            print(f"Current Record: {wins}-{losses} ({wins+losses} games)")
    
    sim_end = time.perf_counter()           
    print(f"\nFinal Record: {wins}-{losses} ({wins+losses} games)")
    print(f"Time taken: {sim_end - sim_start:0.4f} seconds.")

    return

if __name__ == "__main__":
    main()