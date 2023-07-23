import dragonfly as df
import constants, server, game, df_utils

mouse_directions = {
    "sauce": constants.NORTH,
    "ross": constants.EAST,
    "dunce": constants.SOUTH,
    "lease": constants.WEST,
    "tar": constants.NORTHEAST,
    "tis": constants.NORTHWEST,
    "ted": constants.SOUTHEAST,
    "tool": constants.SOUTHWEST,    
}


async def move_mouse_by_tile(direction, n):
    await game.move_mouse_in_direction(direction, n * 64)


non_repeat_mapping = {
    "kick [<positive_num>]": df_utils.async_action(server.mouse_click, "left", "positive_num"),
    "psychic [<positive_num>]": df_utils.async_action(server.mouse_click, "right", "positive_num"),
    "curse <mouse_directions> [<positive_num>]": df_utils.async_action(
        move_mouse_by_tile, "mouse_directions", "positive_num"
    ),
    "short curse <mouse_directions> [<positive_num>]": df_utils.async_action(
        game.move_mouse_in_direction, "mouse_directions", "positive_num"
    ),
    "game state write": df_utils.async_action(game.write_game_state),
    "action": df_utils.async_action(game.press_key, constants.ACTION_BUTTON),
    "(escape | menu [open | close])": df_utils.async_action(game.press_key, constants.MENU_BUTTON),
    "(squat | kick hold)": df_utils.async_action(server.mouse_hold),
    "(bench | kick release)": df_utils.async_action(server.mouse_release),
}


def is_active():
    return True


def load_grammar():
    grammar = df.Grammar("any_context")
    main_rule = df.MappingRule(
        name="any_context_rule",
        mapping=non_repeat_mapping,
        extras=[
            df_utils.positive_num,
            df.Choice("mouse_directions", mouse_directions),
        ],
        context=df.FuncContext(is_active),
        defaults={"positive_num": 1},
    )
    grammar.add_rule(main_rule)
    grammar.load()
