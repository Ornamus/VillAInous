import sys, os, random, time, warnings

from itertools import product
import numpy as np
import IPython

from scipy.stats import pearsonr

import multiprocessing
from multiprocessing import Pool, Manager




class MCTSController(object):

    def __init__(self, T=0.3, C=1.5):#(self, manager, T=0.3, C=1.5):
        super().__init__()

        self.visits = dict()#manager.dict()
        self.differential = dict()#manager.dict()
        self.T = T
        self.C = C

    def record(self, game, score):
        #print(f"add record: {game.strrep()}")
        self.visits["total"] = self.visits.get("total", 1) + 1
        self.visits[game.strrep()] = self.visits.get(game.strrep(), 0) + 1
        self.differential[game.strrep()] = self.differential.get(game.strrep(), 0) + score

    r"""
    Runs a single, random heuristic guided playout starting from a given state. This updates the 'visits' and 'differential'
    counts for that state, as well as likely updating many children states.
    """
    def playout(self, game, expand=150):

        if expand == 0 or game.board.is_game_over():#game.over():
            score = game.GetResult(game.playerToMove)#game.score()
            self.record(game, score)
            #print ('X' if game.turn==1 else 'O', score)
            return score

        action_mapping = {}

        for action in game.GetMoves():
            
            game.DoMove(action)
            action_mapping[action] = self.heuristic_value(game)
            game.UndoMove()

        chosen_action = max(action_mapping, key=action_mapping.get)
        #chosen_action = sample(action_mapping, T=self.T)
        game.DoMove(chosen_action)
        score = -self.playout(game, expand=expand-1) #play branch
        game.UndoMove()
        self.record(game, score)

        return score

    r"""
    Evaluates the "value" of a state as a bandit problem, using the value + exploration heuristic.
    """
    def heuristic_value(self, game):
        N = self.visits.get("total", 1)
        Ni = self.visits.get(game.strrep(), 1e-9)
        V = self.differential.get(game.strrep(), 0)*1.0/Ni 
        return V + self.C*(np.log(N)/Ni)

    r"""
    Evaluates the "value" of a state by randomly playing out games starting from that state and noting the win/loss ratio.
    """
    def value(self, game, playouts=100, steps=5):

        # play random playouts starting from that game value
        with Pool() as p:
            scores = p.map(self.playout, [game.Clone() for i in range(0, playouts)])        
        value = self.differential[game.strrep()]*1.0/self.visits[game.strrep()]
        print(f"value: {value}")
        return value

    r"""
    Chooses the move that results in the highest value state.
    """
    def best_move(self, game, playouts=100):

        action_mapping = {}

        for action in game.GetMoves():
            game.DoMove(action)
            action_mapping[action] = self.value(game, playouts=playouts)
            game.UndoMove()

        print ({a: "{0:.2f}".format(action_mapping[a]) for a in action_mapping})
        return max(action_mapping, key=action_mapping.get)



