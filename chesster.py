import chess
import random
from monte import GameState, ISMCTS
from mcts import MCTSController

class ChessState(GameState):

    def __init__(self, board=None):       
        if board:
            self.board = board
        else:
            self.board = chess.Board()
        
        self.numberOfPlayers = 2
        self.playerToMove = 1
    
    def Clone(self):
        st = ChessState(self.board.copy())
        return st
    
    def CloneAndRandomize(self, observer):
        st = self.Clone()        
        return st
    
    def GetNextPlayer(self, p):
        next = (p % self.numberOfPlayers) + 1
        return next
    
    def DoMove(self, move):
        self.board.push_san(move)
        self.playerToMove = self.GetNextPlayer(self.playerToMove)
    
    def UndoMove(self):
        self.board.pop()
    
    def GetMoves(self):
        if self.board.is_checkmate() or self.board.is_insufficient_material() or self.board.is_game_over():
            return []
        moves = []
        for move in self.board.legal_moves:
            moves.append(move.uci())
        #print(f"{len(moves)} moves")
        return moves
    
    def GetResult(self, player):
        if self.board.is_checkmate() and player != self.playerToMove:
            return 1
        else:
            return 0      
    
    def __repr__(self):
        """ Return a human-readable representation of the state
        """
        return str(self.board)
    
    def strrep(self):
        return str(self.board).replace("\n", "line").replace(" ", "")
    
    def __hash__(self):
        return hash(str(self.board))

if __name__ == "__main__":
    state = ChessState()
    
    mcts = MCTSController()

    while state.GetMoves() != []:
        prev_turn = state.playerToMove  
        print(str(state))
                
        # Use different numbers of iterations (simulations, tree nodes) for different players
        if state.playerToMove == 1:
           # m = mcts.best_move(state, playouts=5)
            #print(f"\Best Move: {m}\n")
            m, node = ISMCTS(rootstate = state, itermax = 1000, verbose = False)
            print(f"Best Move: {m} ({(node.wins/node.visits)*100:.1f}%)\n")
        else:
            m = random.choice(state.GetMoves())
            print(f"\nRandom Move: {m}\n")

        #print(f"Best Move: {m} ({(node.wins/node.visits)*100:.1f}%)\n")
        state.DoMove(m)
    
    print(state)
    if state.board.is_insufficient_material():
        print("Nobody wins!")
    elif state.board.is_checkmate():
        print(f"Somebody got checkmated. Ending turn: {state.playerToMove}. <--- Is that the loser?")
    else:
        print("i don't know.")
        