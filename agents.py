import random
from monte import ISMCTS, AlphaMCTS
import numpy as np

class Agent:

    def GetMove(self, state):
        move = random.choice(state.GetMoves())
        print(f"Random Move: {move}")
        return move, None
        
class ISMCTSAgent(Agent):

    def __init__(self, iterations=500, rollout_agent=None):
        self.iterations = iterations
        self.rollout_agent = rollout_agent

    def GetMove(self, state, moves=None):
        if not moves:
            moves = state.GetMoves()
        #if len(moves) == 1:
            #print(f"ONLY Move: {moves[0]} \n")
            #return moves[0]
        m, node = ISMCTS(rootstate = state, itermax = self.iterations, verbose = False, rollout_agent=self.rollout_agent)
        print(f"Best Move: {m} ({(node.wins/node.visits)*100:.1f}%)\n")
        return m, node   

class AlphaMCTSAgent(Agent):
    
    def __init__(self, iterations=500, model=None):
        self.iterations = iterations
        self.model = model

    def GetMove(self, state, moves=None):
        m, node = AlphaMCTS(rootstate = state, itermax = self.iterations, verbose = False, model = self.model)
        print(f"Best Move: {m}  (state value: {(node.parentNode.nn_value)*100:.1f}%)\n")
        return m, node

class RegressionAgent(Agent):

    def __init__(self, first_random=False, verbose=True):
        super().__init__()
        self.estimator = None
        self.verbose = verbose
        self.first_random = first_random
        
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
            if False:#len(future_state.interrupt_moves) > 0:
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
        
        boards = []
        for data in np.array(inputs):
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
        
        if not self.use_board:
            boards = np.array(inputs)
        
        predictions = self.estimator.model(boards, training=False)#self.estimator.predict(inputs, verbose=0)       
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