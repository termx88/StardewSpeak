import game, server, menu_utils, constants, df_utils
import dragonfly as df

TITLE = 'profileMenu'

mapping = {
    "(character | npc) prior": menu_utils.simple_click('previousCharacterButton'),
    "(character | npc) next": menu_utils.simple_click('nextCharacterButton'),
    "[gift] type prior": menu_utils.simple_click('backButton'),
    "[gift] type next": menu_utils.simple_click('forwardButton')
}

def get_grammar():
    grammar = menu_utils.build_menu_grammar(mapping, TITLE)
    return grammar