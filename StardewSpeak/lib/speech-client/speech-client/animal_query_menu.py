import dragonfly as df
from srabuilder import rules
import menu_utils, server, df_utils, game, objective, server, constants, letters

ANIMAL_QUERY_MENU = 'animalQueryMenu'

mapping = {
    # "pan <direction_keys>": objective.objective_action(objective.HoldKeyObjective, "direction_keys"), # doesn't currently work    
    "yes": menu_utils.simple_click("yesButton"),
    "(ok | shock)": menu_utils.simple_click("yesButton", "okButton"),
    "(no | cancel | escape)": menu_utils.simple_click("noButton"),
    "(pregnancy | reproduction)": menu_utils.simple_click("allowReproductionButton"),
    "sell": menu_utils.simple_click("sellButton"),
    "home [building] (change | move)": menu_utils.simple_click("moveHomeButton"),
    "(name | rename)": menu_utils.simple_click("textBoxCC"),
    **letters.typing_commands()
}

def load_grammar():
    extras = [df.Choice("direction_keys", game.direction_keys), letters.letters_and_keys, df.Dictation("dictation")]
    grammar = menu_utils.build_menu_grammar(mapping, ANIMAL_QUERY_MENU, extras=extras)
    grammar.load()
    
