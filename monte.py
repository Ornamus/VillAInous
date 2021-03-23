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
from keras.models import Sequential
from keras.layers import Dense
from keras.wrappers.scikit_learn import KerasRegressor
from sklearn.model_selection import train_test_split
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import KFold
import os
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
        return "[M:%s W/V/A: %4i/%4i/%4i]" % (self.move, self.wins, self.visits, self.avails)

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

model = None
estimator = None

def init_model():
    global model, estimator
    dataset = loadtxt('game.txt', delimiter=',')
    X = dataset[:,0:32]
    Y = dataset[:,32]

    def baseline_model():
        # create model
        model = Sequential()
        model.add(Dense(32, input_dim=32, kernel_initializer='normal', activation='relu'))
        model.add(Dense(1, kernel_initializer='normal'))
        # Compile model
        model.compile(loss='mean_squared_error', optimizer='adam')
        return model
    # evaluate model
    estimator = KerasRegressor(build_fn=baseline_model, epochs=300, batch_size=50, verbose=2)
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
    global records, estimator, data
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
        while state.GetMoves() != [] and node.GetUntriedMoves(state.GetMoves()) == []: # node is fully expanded and non-terminal
            node = node.UCBSelectChild(state.GetMoves())
            state.DoMove(node.move)
        
        # Expand
        untriedMoves = node.GetUntriedMoves(state.GetMoves())
        if untriedMoves != []: # if we can expand (i.e. state/node is non-terminal)
            m = random.choice(untriedMoves) 
            player = state.playerToMove
            state.DoMove(m)
            node = node.AddChild(m, player) # add child and descend tree
    
        # Simulate
        while state.GetMoves() != []: # while state is non-terminal
            if rollout_agent:
                move = rollout_agent.GetMove(state)
                state.DoMove(move)
            else:
                state.DoMove(random.choice(state.GetMoves()))
        #print(f"{i}/{itermax}")
        # Backpropagate
        while node != None: # backpropagate from the expanded node and work back to the root node
            node.Update(state)
            node = node.parentNode

    # Output some information about the tree - can be omitted
    if (verbose): print(rootnode.TreeToString(0))
    else: print(rootnode.ChildrenToString())
    
    for node in rootnode.childNodes:
        if node.playerJustMoved == 0 and node.visits >= 10:
            potential_state = rootstate.Clone()#
            if node.move in potential_state.GetMoves():
                potential_state.DoMove(node.move)
                record(potential_state, node.wins / node.visits, node.playerJustMoved)

    best_node = max(rootnode.childNodes, key = lambda c: c.visits)
    return best_node.move, best_node # return the move that was most visited


def PlayGame(agents, game_state):
    """ Play a sample game between two ISMCTS players.
    """
    global model, estimator, data_x, data_y, data, records
    from game import ISMCTSAgent
    if estimator is None:
        init_model()
    
    state = game_state
    
    for agent in agents:
        agent.estimator = estimator
        if type(agent).__name__ is ISMCTSAgent.__name__ and agent.rollout_agent != None:
            agent.rollout_agent.estimator = estimator
        
    prev_turn = 0
    while state.GetMoves() != []:
        if prev_turn != state.playerToMove:
            print(f"============ {state.players[state.playerToMove].identifier}'s Turn ===========")
        prev_turn = state.playerToMove  
        print(str(state))
        
        if len(agents) > 0:
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
    
    f = open("game.txt", "a")
    print(f"Records taken: {len(records)}")
    index = 0
    for entry in data_x:
        str_list = [str(element) for element in entry]
        list_str = ",".join(str_list)
        list_str += f",{data_y[index]}\n"
        f.write(list_str)
        #print(f"{entry} -> {data_y[index]}")
        index += 1
    f.close()
    data_x.clear()
    data_y.clear()
    records.clear()
    data.clear()
    
    estimator.model.save("TheModel")
    
    return winner
    
if __name__ == "__main__":
    PlayGame()