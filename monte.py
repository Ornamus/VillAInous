# This is a very simple Python 2.7 implementation of the Information Set Monte Carlo Tree Search algorithm.
# The function ISMCTS(rootstate, itermax, verbose = False) is towards the bottom of the code.
# It aims to have the clearest and simplest possible code, and for the sake of clarity, the code
# is orders of magnitude less efficient than it could be made, particularly by using a 
# state.GetRandomMove() or state.DoRandomRollout() function.
# 
# An example GameState classes for Knockout Whist is included to give some idea of how you
# can write your own GameState to use ISMCTS in your hidden information game.
# 
# Written by Peter Cowling, Edward Powley, Daniel Whitehouse (University of York, UK) September 2012 - August 2013.
# 
# Licence is granted to freely use and distribute for any sensible/legal purpose so long as this comment
# remains in any distributed code.
# 
# For more information about Monte Carlo Tree Search check out our web site at www.mcts.ai
# Also read the article accompanying this code at ***URL HERE***

from math import *
import random, sys
from copy import deepcopy
from numpy import loadtxt
import numpy as np
from tensorflow.keras import datasets, layers, models
from keras.models import Sequential, load_model
from keras.layers import Dense
from keras.wrappers.scikit_learn import KerasRegressor
from sklearn.model_selection import train_test_split
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import KFold
import tensorflow as tf
import os
import time
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

class GameState:
    """ A state of the game, i.e. the game board. These are the only functions which are
        absolutely necessary to implement ISMCTS in any imperfect information game,
        although they could be enhanced and made quicker, for example by using a 
        GetRandomMove() function to generate a random move during rollout.
        By convention the players are numbered 1, 2, ..., self.numberOfPlayers.
    """
    def __init__(self):
        self.numberOfPlayers = 2
        self.playerToMove = 1
    
    def GetNextPlayer(self, p):
        """ Return the player to the left of the specified player
        """
        return (p % self.numberOfPlayers) + 1
    
    def Clone(self):
        """ Create a deep clone of this game state.
        """
        st = GameState()
        st.playerToMove = self.playerToMove
        return st
    
    def CloneAndRandomize(self, observer):
        """ Create a deep clone of this game state, randomizing any information not visible to the specified observer player.
        """
        return self.Clone()
    
    def DoMove(self, move):
        """ Update a state by carrying out the given move.
            Must update playerToMove.
        """
        self.playerToMove = self.GetNextPlayer(self.playerToMove)
        
    def GetMoves(self):
        """ Get all possible moves from this state.
        """
        raise NotImplementedException()
    
    def GetResult(self, player):
        """ Get the game result from the viewpoint of player. 
        """
        raise NotImplementedException()

    def __repr__(self):
        """ Don't need this - but good style.
        """
        pass


class Node:
    """ A node in the game tree. Note wins is always from the viewpoint of playerJustMoved.
    """
    def __init__(self, move = None, parent = None, playerJustMoved = None):
        self.move = move # the move that got us to this node - "None" for the root node
        self.parentNode = parent # "None" for the root node
        self.childNodes = []
        self.wins = 0
        self.visits = 0
        self.avails = 1
        self.playerJustMoved = playerJustMoved # the only part of the state that the Node needs later
        # NN stuff
        self.nn_w = 0
        self.nn_q = 0
        self.nn_value = 0
        self.target_value = 0
        self.nn_pred_prob = 0
        self.target_prob = 0
    
    def GetUntriedMoves(self, legalMoves):
        """ Return the elements of legalMoves for which this node does not have children.
        """
        
        # Find all moves for which this node *does* have children
        triedMoves = [child.move for child in self.childNodes]
        
        # Return all moves that are legal but have not been tried yet
        return [move for move in legalMoves if move not in triedMoves]
        
    def UCBSelectChild(self, legalMoves, exploration = 0.7):
        """ Use the UCB1 formula to select a child node, filtered by the given list of legal moves.
            exploration is a constant balancing between exploitation and exploration, with default value 0.7 (approximately sqrt(2) / 2)
        """
        
        # Filter the list of children by the list of legal moves
        legalChildren = [child for child in self.childNodes if child.move in legalMoves]
        
        # Get the child with the highest UCB score
        s = max(legalChildren, key = lambda c: float(c.wins)/float(c.visits) + exploration * sqrt(log(c.avails)/float(c.visits)))
        
        # Update availability counts -- it is easier to do this now than during backpropagation
        for child in legalChildren:
            child.avails += 1
        
        # Return the child selected above
        return s
    
    def NNSelectChild(self, legalMoves, exploration = 0.7):       
        # Filter the list of children by the list of legal moves
        legalChildren = [child for child in self.childNodes if child.move in legalMoves]
        
        child_visits_sum = 0
        for child in legalChildren:
            child_visits_sum += child.visits
        
        # action-value +  exploration * prior_prob * [weird stuff]
        s = max(legalChildren, key = lambda c: c.nn_q + exploration * c.nn_pred_prob * sqrt(child_visits_sum)/(1+c.visits))
        
        # Update availability counts -- it is easier to do this now than during backpropagation
        for child in legalChildren:
            child.avails += 1
        
        # Return the child selected above
        return s
    
    def AddChild(self, m, p):
        """ Add a new child node for the move m.
            Return the added child node
        """
        n = Node(move = m, parent = self, playerJustMoved = p)
        self.childNodes.append(n)
        return n
    
    def Update(self, terminalState):
        """ Update this node - increment the visit count by one, and increase the win count by the result of terminalState for self.playerJustMoved.
        """
        self.visits += 1
        if self.playerJustMoved is not None:
            self.wins += terminalState.GetResult(self.playerJustMoved)

    def __repr__(self):
        #if self.nn_q == 0 and self.nn_value == 0 and self.nn_w == 0 and self.target_prob == 0:
            #return "[M:%s W/V/A: %4i/%4i/%4i]" % (self.move, self.wins, self.visits, self.avails)
        #else:
        
        return f"[M:{self.move} W/Q/V/P:  {self.nn_value:4.1f} / {self.nn_q:4.1f} / {self.visits:4} / {self.nn_pred_prob:4.1f}"


    def TreeToString(self, indent):
        """ Represent the tree as a string, for debugging purposes.
        """
        s = self.IndentString(indent) + str(self)
        for c in self.childNodes:
            s += c.TreeToString(indent+1)
        return s

    def IndentString(self,indent):
        s = "\n"
        for i in range (1,indent+1):
            s += "| "
        return s

    def ChildrenToString(self):
        s = ""
        for c in self.childNodes:
            s += str(c) + "\n"
        return s

def get_model(model_type, train=False):
    if train:
        dataset = loadtxt('game.txt', delimiter=',')
        print(f"len: {len(dataset[0])}")
        X = dataset[:,0:42] #42
        Y = dataset[:,42:]
        print(f"Top Y: {Y[0]}")
    
    def flat_model():
        model = Sequential()
        model.add(Dense(42, input_dim=42, kernel_initializer='normal', activation='relu'))
        model.add(Dense(8, kernel_initializer='normal'))
        model.compile(loss='mean_squared_error', optimizer='adam')
        return model
    
    def baseline_model():
        model = models.Sequential()
        model.add(layers.Conv2D(32, (3, 3), activation='relu', input_shape=(6,7,1)))
        model.add(layers.MaxPooling2D((2, 2)))
        #model.add(layers.Conv2D(64, (3, 3), activation='relu'))
        #model.add(layers.MaxPooling2D((2, 2)))
        #model.add(layers.Conv2D(32, (3, 3), activation='relu'))
        model.add(layers.Flatten())
        model.add(layers.Dense(64, activation='relu'))
        model.add(layers.Dense(8))
        
        model.compile(
          'adam',
          loss='mean_squared_error',
        )
        model.summary()
        return model
    
    if train and model_type == 1:
        boards = []
        for data in X:
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
        #print(boards)
        
    if model_type == 0:
        estimator = KerasRegressor(build_fn=flat_model, epochs=5000, batch_size=100, verbose=2)
        if train:
            estimator.fit(X, Y)
            estimator.model.save("Con4_Flat_Recent.h5")
        else:
            estimator.model = load_model('Con4_Flat_Recent.h5')#load_model('Con4_Flat_Best.h5')
        return estimator
    elif model_type == 1:
        estimator = KerasRegressor(build_fn=baseline_model, epochs=300, batch_size=100, verbose=2)   
        if train:
            estimator.fit(boards, Y)
            estimator.model.save("Con4_Conv_Recent.h5")
        else:
            estimator.model = load_model('Con4_Conv_Recent.h5')
        return estimator
    return None
        

def init_model_villainous():
    global model, estimator
    dataset = loadtxt('game.txt', delimiter=',')
    X = dataset[:,0:460]
    Y = dataset[:,460]

    def baseline_model():
        # create model
        model = Sequential()
        model.add(Dense(460, input_dim=460, kernel_initializer='normal', activation='relu'))
        model.add(Dense(1, kernel_initializer='normal'))
        # Compile model
        model.compile(loss='mean_squared_error', optimizer='adam')
        return model
    # evaluate model
    estimator = KerasRegressor(build_fn=baseline_model, epochs=400, batch_size=50, verbose=2)
    print(f"Type of x: {type(X)}, Y: {type(Y)}")
    estimator.fit(X, Y)
    estimator.model.save("TheModel")
    #estimator.fit(X[0:1,:], Y[0:1], epochs=1, batch_size=1)
    return
    kfold = KFold(n_splits=10)
    results = cross_val_score(estimator, X, Y, cv=kfold)
    print("Baseline: %.2f (%.2f) MSE" % (results.mean(), results.std()))
    estimator.fit(X, Y)
    
    return


records = []
data = []
data_x = []
data_y = []
def record(state, result, player):
    global records, data, estimator
    records.append((state, result))
    
    entry = state.to_inputs(player)
    data_x.append(entry)
    data_y.append(result)    
    
    #estimator.fit(np.array([entry]), np.array([result]), epochs=1, batch_size=1)

    entry = deepcopy(entry)
    entry.append(result)
    data.append(entry)
    

def ISMCTS(rootstate, itermax, verbose = False, rollout_agent=None):
    """ Conduct an ISMCTS search for itermax iterations starting from rootstate.
        Return the best move from the rootstate.
    """

    rootnode = Node()
    #rollout_agent = RegressionAgent(estimator)

    for i in range(itermax):
        node = rootnode
        
        # Determinize
        state = rootstate.CloneAndRandomize(rootstate.playerToMove)

        # Select
        moves = state.GetMoves()
        while moves != [] and node.GetUntriedMoves(moves) == []: # node is fully expanded and non-terminal
            node = node.UCBSelectChild(state.GetMoves())
            state.DoMove(node.move)
            moves = state.GetMoves()

        # Expand
        untriedMoves = node.GetUntriedMoves(moves) # state.GetMoves()
        if untriedMoves != []: # if we can expand (i.e. state/node is non-terminal)
            if rollout_agent:
                m = rollout_agent.GetMove(state, moves=untriedMoves)
            else:
                m = random.choice(untriedMoves) 
            player = state.playerToMove
            state.DoMove(m)
            node = node.AddChild(m, player) # add child and descend tree

        # Simulate
        
        moves = state.GetMoves()
        move_time = 0
        while moves != []: # while state is non-terminal
            if rollout_agent:
                move = rollout_agent.GetMove(state, moves=moves)
                state.DoMove(move)                
            else:
                state.DoMove(random.choice(moves))
            moves = state.GetMoves()

        # Backpropagate
        while node != None: # backpropagate from the expanded node and work back to the root node
            node.Update(state)
            node = node.parentNode

    # Output some information about the tree - can be omitted
    if (verbose): print(rootnode.TreeToString(0))
    else: print(rootnode.ChildrenToString())
    
    if True:
        for node in rootnode.childNodes:
            if node.visits >= 10:
                potential_state = rootstate.Clone()#
                if node.move in potential_state.GetMoves():
                    potential_state.DoMove(node.move)
                    record(potential_state, node.wins / node.visits, node.playerJustMoved)


    total_visits = 0
    for node in rootnode.childNodes:
        total_visits += node.visits
    for node in rootnode.childNodes:
        node.target_prob = node.visits / total_visits
        #if node.target_prob > 0 :
            #print(f"prob: {node.target_prob}")

    best_node = max(rootnode.childNodes, key = lambda c: c.visits)
    return best_node.move, best_node # return the move that was most visited

def AlphaMCTS(rootstate, itermax, verbose = False, model=None):
    """ Conduct an ISMCTS search for itermax iterations starting from rootstate.
        Return the best move from the rootstate.
        https://www.reddit.com/r/reinforcementlearning/comments/cc5mv4/how_to_incorporate_neural_networks_into_a_mcts/
        https://matthewdeakos.me/2018/07/03/integrating-monte-carlo-tree-search-and-neural-networks/
    """
    
    rootnode = Node()

    for i in range(itermax):
        node = rootnode
        
        # Determinize
        state = rootstate.CloneAndRandomize(rootstate.playerToMove)
        player = state.playerToMove
        # Select
        moves = state.GetMoves()
        while moves != [] and node.GetUntriedMoves(moves) == [] and node.nn_value > 0: # node is fully expanded and non-terminal
            node = node.NNSelectChild(state.GetMoves())
            state.DoMove(node.move)
            moves = state.GetMoves()
        
        # The steps 2 and 3 are replaced by a policy and value network: 
        # we expand all the child nodes with probability priors given by the network, 
        # and instead of simulating the whole game onwards, simply use the value output. 
        # To increase exploration in self play, instead of selecting the most visited move,
        # you can select it with some temperature on a soft max you sample.
        
        untriedMoves = node.GetUntriedMoves(moves)
        if untriedMoves != []:
            value, prob_priors = state.predict(model, node.playerJustMoved, use_boards=True)
            node.nn_value = value
            for i in range(0, len(moves)):
                move = moves[i]
                if move in untriedMoves:
                    child = node.AddChild(move, state.GetNextPlayer(state.playerToMove))
                    #print(f"setting a prior to {prob_priors[i]}")
                    child.nn_pred_prob = prob_priors[i]
        leaf = node
        # Backpropagate
        while node != None: # backpropagate from the expanded node and work back to the root node
            node.visits += 1
            
            # If the player that owns node is the same player that owns the leaf node, then we add v to w. Otherwise, we subtract v from w.
            node.nn_w += leaf.nn_value * (-1 if leaf.playerJustMoved != node.playerJustMoved else 1)
            
            # We update the action-value q to w/visits.
            node.nn_q = node.nn_w / node.visits
            
            node = node.parentNode

    # Output some information about the tree - can be omitted
    if (verbose): print(rootnode.TreeToString(0))
    else: print(rootnode.ChildrenToString())
    
    # TODO: add temperature here eventually?
    total_visits = 0
    for node in rootnode.childNodes:
        total_visits += node.visits
    for node in rootnode.childNodes:
        if total_visits > 0:
            node.target_prob = node.visits / total_visits
        else:
            node.target_prob = 0
    
    best_node = max(rootnode.childNodes, key = lambda c: c.target_prob) 
    return best_node.move, best_node # return the move that was most visited

def PlayGame(agents, game_state):
    """ Play a sample game between two ISMCTS players.
    """
    global model, estimator, data_x, data_y, data, records
    from agents import ISMCTSAgent

    #tf.keras.backend.set_learning_phase(0)
    state = game_state
    
    first = True  
    game_over = False
    prev_turn = 0
    first_move_ever = True
    while not game_over and state.GetMoves() != []:
        if prev_turn != state.playerToMove:
            print(f"============ Player {state.playerToMove}'s Turn ===========")
            #print(f"============ {state.players[state.playerToMove].identifier}'s Turn ===========")
        prev_turn = state.playerToMove  
        print(str(state))
        
        if len(agents) > 0:
            agent = agents[state.playerToMove]
            if first_move_ever and hasattr(agent, 'first_random') and agent.first_random:
                m = random.choice(state.GetMoves())
            else:
                m = agents[state.playerToMove].GetMove(state)
        else:
            # Use different numbers of iterations (simulations, tree nodes) for different players
            if state.playerToMove == 0:
                m, node = ISMCTS(rootstate = state, itermax = 500, verbose = False)
                print(f"Best Move: {m} ({(node.wins/node.visits)*100:.1f}%)\n")
                future_state = state.CloneAndRandomize(state.playerToMove)
                future_state.DoMove(m)
                prediction = estimator.predict([future_state.to_inputs(node.playerJustMoved)])
                print(f"Model prediction: {prediction}")
            else:
                m, node = ISMCTS(rootstate = state, itermax = 500, verbose = False)
                print(f"Best Move: {m} ({(node.wins/node.visits)*100:.1f}%)\n")
                #m = random.choice(state.GetMoves())
                #print(f"\nRandom Move: {m}\n")

        state.DoMove(m)
        first_move_ever = False
        for i in range(0, state.numberOfPlayers):
            if state.GetResult(i) == 1:
                game_over = True
                break
        #for player in state.players:
            #if player.has_won(state):
                #game_over = True
                #break
   
    someoneWon = False
    nums = range(0, state.numberOfPlayers)
    
    winner = None
    for p in nums:
        if state.GetResult(p) > 0:
            print("Player " + str(p) + " wins!")
            winner = p
            someoneWon = True
    if not someoneWon:
        print("Nobody wins!")
    
    #save_records = True
    #if save_records:
    #f = open("game.txt", "a")
    print(f"Records taken: {len(records)}")
    if len(data_x) > 0:
        print(f"Input length: {len(data_x[0])}")
    index = 0
    for entry in data_x:
        str_list = [str(element) for element in entry]
        list_str = ",".join(str_list)
        list_str += f",{data_y[index]}\n"
        #f.write(list_str)
        index += 1
    #f.close()
    data_x.clear()
    data_y.clear()
    records.clear()
    data.clear()
    #if estimator:
        #estimator.model.save("TheModel")
    
    return winner

def SelfPlayGame(agents, game_state):
    player_moves = []
    for agent in agents:
        player_moves.append([])
    state = game_state
    game_over = False
    prev_turn = 0
    while not game_over and state.GetMoves() != []:
        if prev_turn != state.playerToMove:
            print(f"============ Player {state.playerToMove}'s Turn ===========")
        prev_turn = state.playerToMove  
        print(str(state))
        
        agent = agents[state.playerToMove]
        m, node = agents[state.playerToMove].GetMove(state)
        if node:
            player_moves[state.playerToMove].append((node, state.Clone()))

        state.DoMove(m)
        for i in range(0, state.numberOfPlayers):
            if state.GetResult(i) == 1:
                game_over = True
                break
   
    someoneWon = False
    
    winner = None
    for p in range(0, state.numberOfPlayers):
        if state.GetResult(p) > 0:
            print("Player " + str(p) + " wins!")
            winner = p
            someoneWon = True
    if not someoneWon:
        print("Nobody wins!")
    return winner
    data = []
    
    f = open("game.txt", "a")
    
    for p in range(0, state.numberOfPlayers):
        for node, state in player_moves[p]:
            
            node.target_value = 1 if winner == p else (-1 if winner is not None else 0)          
            target_policy = [0] * 7
            for n in node.parentNode.childNodes:
                target_policy[n.move] = n.target_prob

            
            data.append((state, node.target_value, target_policy))
            inputs = state.to_inputs(p)
            inputs.append(node.target_value)
            inputs.extend(target_policy)
            
            str_list = [str(element) for element in inputs]
            list_str = ",".join(str_list) + "\n"
            f.write(list_str)
    f.close()
    return winner
    
if __name__ == "__main__":
    PlayGame()