import dragonfly as df
import functools
from srabuilder import rules
import characters, locations, fishing_menu, title_menu, menu_utils, server, df_utils, game, container_menu, objective, constants, items
import tts

mouse_directions = {
    "sauce": "up",
    "ross": "right",
    "dunce": "down",
    "lease": "left",
}


async def get_objects_by_name(name: str, loc: str):
    objs = await game.get_location_objects("")
    return [x for x in objs if x["name"] == name]


async def go_to_object(item: items.Item, index):
    obj_getter = functools.partial(get_objects_by_name, item.name)
    await game.navigate_nearest_tile(obj_getter, index=index)


async def move_and_face_previous_direction(direction: int, n: int):
    async with server.player_status_stream() as stream:
        ps = await stream.next()
        await game.move_n_tiles(direction, n, stream)
        await game.face_direction(ps["facingDirection"], stream, move_cursor=True)


async def get_shipping_bin_tiles(item):
    tile = await server.request("SHIPPING_BIN_TILE")
    return game.break_into_pieces([tile])


async def go_to_shipping_bin():
    await game.navigate_nearest_tile(get_shipping_bin_tiles)
    await game.do_action()


async def get_bed_tile(item):
    tile = await server.request("BED_TILE")
    return [tile]


async def go_to_bed():
    await game.navigate_nearest_tile(get_bed_tile, pathfind_fn=game.pathfind_to_tile)


async def get_ladders_down(item):
    return await server.request("GET_LADDERS_DOWN")


async def ladder_down():
    await game.navigate_nearest_tile(get_ladders_down)
    await game.do_action()


async def navigate_direction(direction: int):
    async with server.player_status_stream() as stream:
        player_status = await stream.next()
        location = player_status["location"]
        path_tiles = await server.request("PATH_TO_EDGE", {"direction": direction})
        if path_tiles:
            path = game.Path(path_tiles, location)
            await path.travel(stream)


async def pet_farm_pet():
    pass


numrep2 = df.Sequence(
    [df.Choice(None, rules.nonZeroDigitMap), df.Repetition(df.Choice(None, rules.digitMap), min=0, max=10)],
    name="n2",
)
num2 = df.Modifier(numrep2, rules.parse_numrep)

debris = {
    "(stones | rocks)": constants.STONE,
    "(wood | twigs)": constants.TWIG,
    "weeds": constants.WEEDS,
    "debris": "debris",
}

mapping = {
    "<direction_keys>": objective.objective_action(objective.HoldKeyObjective, "direction_keys"),
    "<direction_nums> <n>": objective.objective_action(objective.MoveNTilesObjective, "direction_nums", "n"),
    "kick hold": objective.objective_action(objective.HoldKeyObjective, constants.USE_TOOL_BUTTON),
    "item <positive_index> [equip]": df_utils.async_action(game.equip_item_by_index, "positive_index"),
    "[melee] weapon equip": df_utils.async_action(game.equip_melee_weapon),
    "<items> equip": df_utils.async_action(game.equip_item_by_name, "items"),
    "nearest <items> [<positive_index>]": objective.function_objective(go_to_object, "items", "positive_index"),
    "(strafe | jump) <direction_nums> [<positive_num>]": df_utils.async_action(
        move_and_face_previous_direction, "direction_nums", "positive_num"
    ),
    "bed go": objective.function_objective(go_to_bed),
    "shipping bin [go]": objective.function_objective(go_to_shipping_bin),
    "shopping [start]": objective.function_objective(objective.start_shopping),
    "crops water": objective.objective_action(objective.WaterCropsObjective),
    "crops harvest": objective.objective_action(objective.HarvestCropsObjective),
    "(quests | journal | quest log) [open | read]": df_utils.async_action(game.press_key, constants.JOURNAL_BUTTON),
    "turn <direction_nums>": objective.objective_action(objective.FaceDirectionObjective, "direction_nums"),
    "stop": df_utils.async_action(server.stop_everything),
    "swing": df_utils.async_action(game.press_key, constants.USE_TOOL_BUTTON),
    "toolbar next": df_utils.async_action(game.press_key, constants.TOOLBAR_SWAP),
    "<points>": objective.function_objective(objective.move_to_point, "points"),
    "trees chop": objective.objective_action(objective.ChopTreesObjective),
    "((this | crops) plant | planting start)": objective.objective_action(objective.PlantSeedsOrFertilizerObjective),
    "<debris> clear": objective.objective_action(objective.ClearDebrisObjective, "debris"),
    "grass clear": objective.objective_action(objective.ClearGrassObjective),
    "ore (clear | dig | mine)": objective.objective_action(objective.ClearOreObjective),
    "attack": objective.objective_action(objective.AttackObjective),
    "defend": objective.objective_action(objective.DefendObjective),
    "ladder (down | dunce) [go]": objective.function_objective(ladder_down),
    "<n> by <n2> (hoe | dig)": objective.objective_action(objective.HoePlotObjective, "n", "n2"),
    "<npcs> talk": objective.objective_action(objective.TalkToNPCObjective, "npcs"),
    "[watering] can refill": objective.function_objective(game.refill_watering_can),
    "crafting collect": objective.function_objective(game.gather_crafted_items),
    "forage": objective.function_objective(game.gather_forage_items),
    "(objects | items) collect": objective.function_objective(game.gather_objects),
    "(artifact | artifacts) dig": objective.function_objective(game.dig_artifacts),
    "inside go": objective.function_objective(game.go_inside),
    "outside go": objective.function_objective(game.go_outside),
    "animals pet": objective.function_objective(objective.pet_animals),
    "animals milk": objective.function_objective(objective.use_tool_on_animals, constants.MILK_PAIL),
    "fishing start": objective.function_objective(fishing_menu.start_fishing),
    "navigate <direction_nums>": objective.function_objective(navigate_direction, "direction_nums"),
}


@menu_utils.valid_menu_test
def is_active():
    return game.get_context_menu() is None


def load_grammar():
    grammar = df.Grammar("no_menu")
    main_rule = df.MappingRule(
        name="no_menu_rule",
        mapping=mapping,
        extras=[
            rules.num,
            df_utils.positive_index,
            df_utils.positive_num,
            df.Choice("npcs", characters.npcs),
            num2,
            df.Choice("direction_keys", game.direction_keys),
            df.Choice("direction_nums", game.direction_nums),
            df.Choice("debris", debris),
            items.items_choice,
            df.Choice("points", locations.commands(locations.points)),
        ],
        context=is_active,
        defaults={"n": 1, "positive_num": 1, "positive_index": 0},
    )
    grammar.add_rule(main_rule)
    grammar.load()
