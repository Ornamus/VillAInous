class Move:
    
    def __init__(self, parent_action):
        self.parent_action = parent_action

    def perform(self, game_state, player):
        pass
	
    def __str__(self):
        return f"Blank Move ({type(self.parent_action)})"

    def __eq__(self, other):
        #if type(self) is Move:
            #return type(other) is Move
        return type(self) is type(other) and type(self.parent_action) is type(other.parent_action)
    
    def __ne__(self, other):
        #if type(self) is Move:
            #return type(other) is not Move
        return type(self) is not type(other) or type(self.parent_action) is not type(other.parent_action)
    
class MoveZoneMove(Move):

    def __init__(self, zone):
        super().__init__(None)
        self.zone = zone
    
    def perform(self, game_state, player):
        player.board_position = self.zone
 
    def __str__(self):
        return f"Move to zone {self.zone.number}"
        
    def __eq__(self, other):
        return self.zone.number == other.zone.number
    
    def __ne__(self, other):
        return self.zone.number != other.zone.number

class PlayCardMove(Move):

    def __init__(self, card, parent_action):
        super().__init__(self, parent_action)
        self.card = card
    
    def perform(self, game_state, player):
        player.board_position = zone
        
    def __str__(self):
        return "Play card {self.card.name}"