# import time
import re
import functools
import async_timeout
import contextlib
import traceback
import weakref
import functools
import queue
import sys
import asyncio
import threading
import uuid
import json
import server
from dragonfly import *
from srabuilder import rules

import constants, server, game, df_utils

active_objective = None
pending_objective = None

def get_active_objective():
    return active_objective

class ObjectiveQueue:

    def __init__(self):
        self.objectives = []

    def clear(self):
        self.objectives.clear()

class ObjectiveFailedError(BaseException):
    pass


class Objective:

    def add_task(self, coro):
        task_wrapper = server.TaskWrapper(coro)
        self.tasks.append(task_wrapper)
        return task_wrapper

    @property
    def tasks(self):
        if not hasattr(self, '_tasks'):
            self._tasks = []
        return self._tasks

    async def run(self):
        raise NotImplementedError

    async def wrap_run(self):
        name = self.__class__.__name__
        server.log(f"Starting objective {name}")
        self.run_task = server.TaskWrapper(self.run())
        await self.run_task.task
        if self.run_task.exception:
            if isinstance(self.run_task.exception, (Exception, ObjectiveFailedError)):
                server.log(f"Objective {name} errored: \n{self.run_task.exception_trace}")
            elif isinstance(self.run_task.exception, asyncio.CancelledError):
                server.log(f"Canceling objective {name}")
            await game.release_all_keys()
        else:
            server.log(f"Successfully completed objective {name}")
        for task_wrapper in self.tasks:
            await task_wrapper.cancel()

    def fail(self, msg=None):
        if msg is None:
            msg = "Objective {self.__class__.__name__} failed"
        raise ObjectiveFailedError(msg)

class FunctionObjective(Objective):

    def __init__(self, fn, *a, **kw):
        self.fn = fn
        self.a = a
        self.kw = kw

    async def run(self):
        await self.fn(*self.a, **self.kw)

class HoldKeyObjective(Objective):
    def __init__(self, keys):
        self.keys = keys

    async def run(self):
        async with game.press_and_release(self.keys):
            # infinite loop to indicate that the objective isn't done until task is canceled
            await server.sleep_forever()

class FaceDirectionObjective(Objective):
    def __init__(self, direction):
        self.direction = direction

    async def run(self):
        async with server.player_status_stream() as stream:
            await game.face_direction(self.direction, stream, move_cursor=True)


class MoveNTilesObjective(Objective):
    def __init__(self, direction, n):
        self.direction = direction
        self.n = n

    async def run(self):
        async with server.player_status_stream(ticks=1) as stream:
            await game.move_n_tiles(self.direction, self.n, stream)

class MoveToLocationObjective(Objective):
    def __init__(self, location):
        self.location = location

    async def run(self):
        async with server.player_status_stream() as stream:
            await game.move_to_location(self.location.name, stream)

async def move_to_point(point):
    async with server.player_status_stream() as stream:
        player_status = await stream.next()
        regex_mismatch = isinstance(point.location, re.Pattern) and not point.location.match(player_status['location'])
        str_mismatch = isinstance(point.location, str) and point.location != player_status['location']
        if regex_mismatch or str_mismatch:
            raise game.NavigationFailed(f'Currently in {player_status["location"]} - unable to move to point in location {point.location}')
        await game.navigate_nearest_tile(point.get_tiles, pathfind_fn=point.pathfind_fn)
        if point.on_arrival:
            await point.on_arrival()

class ChopTreesObjective(Objective):

    def __init__(self):
        pass

    async def run(self):
        await game.equip_item_by_name(constants.AXE)
        async for tree in game.navigate_tiles(game.get_fully_grown_trees_and_stumps, game.generic_next_item_key):
            await game.chop_tree_and_gather_resources(tree)
class WaterCropsObjective(Objective):

    def __init__(self):
        pass

    async def get_unwatered_crops(self, location: str):
        hoe_dirt_tiles = await game.get_hoe_dirt('')
        tiles_to_water = [hdt for hdt in hoe_dirt_tiles if hdt['crop'] and not hdt['isWatered'] and hdt['needsWatering']]
        return tiles_to_water

    async def run(self):
        await game.equip_item_by_name(constants.WATERING_CAN)
        async for crop in game.navigate_tiles(self.get_unwatered_crops, game.generic_next_item_key):
            await game.swing_tool()

class HarvestCropsObjective(Objective):

    async def get_harvestable_crops(self, location: str):
        hoe_dirt_tiles = await game.get_hoe_dirt('')
        harvestable_crop_tiles = [hdt for hdt in hoe_dirt_tiles if hdt['crop'] and hdt['readyForHarvest']]
        return harvestable_crop_tiles

    async def run(self):
        async for crop in game.navigate_tiles(self.get_harvestable_crops, game.generic_next_item_key):
            await game.do_action()


class ClearDebrisObjective(Objective):

    def __init__(self):
        pass

    async def get_debris(self, location):
        debris_objects, resource_clumps, tools = await asyncio.gather(self.get_debris_objects(location), game.get_resource_clump_pieces(location), game.get_tools(), loop=server.loop)
        debris = debris_objects + resource_clumps
        clearable_debris = []
        for d in debris:
            required_tool = game.tool_for_object[d['name']]
            tool = tools.get(required_tool['name'])
            if tool and tool['upgradeLevel'] >= required_tool['level']:
                clearable_debris.append(d)
        return clearable_debris

    async def get_debris_objects(self, location):
        objs = await game.get_location_objects(location)
        debris = [{**o, 'type': 'object'} for o in objs if game.is_debris(o)]
        return debris

    async def at_tile(self, obj):
        needed_tool = game.tool_for_object[obj['name']]
        await game.equip_item_by_name(needed_tool['name'])
        if obj['type'] == 'object':
            await game.clear_object(obj, self.get_debris_objects)
        else:
            assert obj['type'] == 'resource_clump'
            await game.clear_object(obj, game.get_resource_clump_pieces)
        if obj['type'] == 'resource_clump':
            await game.gather_items_on_ground(6)

    async def run(self):
        async for debris in game.navigate_tiles(self.get_debris, game.next_debris_key):
            await self.at_tile(debris)

class PlantSeedsOrFertilizerObjective(Objective):

    def __init__(self):
        pass

    async def get_hoe_dirt(self, location: str):
        hoe_dirt_tiles = await game.get_hoe_dirt('')
        return [x for x in hoe_dirt_tiles if x['canPlantThisSeedHere']]

    async def run(self):
        async for hdt in game.navigate_tiles(self.get_hoe_dirt, game.generic_next_item_key):
            await game.do_action()
class HoePlotObjective(Objective):

    def __init__(self, n1, n2):
        self.n1 = n1
        self.n2 = n2

    async def run(self):
        async with server.player_status_stream() as stream:
            await game.equip_item_by_name(constants.HOE)
            player_status = await stream.next()
        player_tile = player_status["tileX"], player_status["tileY"]
        facing_direction = player_status['facingDirection']
        start_tile = game.next_tile(player_tile, facing_direction)
        plot_tiles = set()
        x_increment = -1 if game.last_faced_east_west == constants.WEST else 1
        y_increment = -1 if game.last_faced_north_south == constants.NORTH else 1
        for i in range(self.n1):
            x = start_tile[0] + i * x_increment
            for j in range(self.n2):
                y = start_tile[1] + j * y_increment
                plot_tiles.add((x, y))
        get_next_diggable = functools.partial(game.get_diggable_tiles, plot_tiles)
        async for hdt in game.navigate_tiles(get_next_diggable, game.generic_next_item_key):
            await game.swing_tool()


class TalkToNPCObjective(Objective):

    def __init__(self, npc_name):
        self.npc_name = npc_name

    async def run(self):
        async with server.characters_at_location_stream() as npc_stream:
            fn = functools.partial(game.find_npc_by_name, self.npc_name, npc_stream)
            await game.move_to_character(fn)
        await game.do_action()

async def use_tool_on_animals(tool: str, animal_type=None):
    async with server.animals_at_location_stream() as animals_stream, server.player_status_stream() as player_stream:
        await game.equip_item_by_name(tool)
        consecutive_errors = 0
        consecutive_error_threshold = 5
        while True:
            animals = await game.get_animals(animals_stream, player_stream)
            animal = next((x for x in animals if x["isMature"] and x['currentProduce'] > 0 and x['toolUsedForHarvest'] == tool), None)
            if not animal:
                return
            fn = functools.partial(game.find_animal_by_name, animal['name'], animals_stream)
            try:
                await game.move_to_character(fn)
            except game.NavigationFailed:
                consecutive_errors += 1
            else:
                did_use = await game.use_tool_on_animal_by_name(animal['name'])
                if not did_use:
                    consecutive_errors += 1
                else:
                    consecutive_errors = 0
                await asyncio.sleep(0.1)
            if consecutive_errors >= consecutive_error_threshold:
                raise RuntimeError()

async def pet_animals():
    async with server.animals_at_location_stream() as animals_stream, server.player_status_stream() as player_stream:
        while True:
            animals = await game.get_animals(animals_stream, player_stream)
            animal = next((x for x in animals if not x["wasPet"]), None)
            if not animal:
                return
            fn = functools.partial(game.find_animal_by_name, animal['name'], animals_stream)
            try:
                res = await game.move_to_character(fn)
            except game.NavigationFailed:
                continue
            if res:
                await game.pet_animal_by_name(animal['name'])
                await asyncio.sleep(0.1)
        
class DefendObjective(Objective):

    async def run(self):
        async with server.characters_at_location_stream() as char_stream, server.player_status_stream() as player_stream:
            player_position = (await player_stream.next())['position']
            while True:
                chars = await char_stream.next()
                monsters = [x for x in chars if x['isMonster']]
                if not monsters:
                    return
                visible_monster_positions = [x['position'] for x in chars if not x['isInvisible']]
                if not visible_monster_positions:
                    continue
                if player_stream.has_value:
                    player_position = player_stream.latest_value['position']
                visible_monster_positions.sort(key=lambda x: game.distance_between_tiles_diagonal(player_position, x))
                closest_monster_position = visible_monster_positions[0]
                distance_from_monster = game.distance_between_tiles_diagonal(player_position, closest_monster_position)
                if distance_from_monster > 0:
                    direction_to_face = game.direction_from_positions(player_position, closest_monster_position)
                    await game.face_direction(direction_to_face, player_stream)
                if distance_from_monster < 110:
                    await game.swing_tool()

class AttackObjective(Objective):

    def __init__(self):
        self.player_position = None
        self.invisible_monsters = []

    async def run(self):
        async with server.characters_at_location_stream() as char_stream, server.player_status_stream() as player_stream:
            get_monster = functools.partial(self.get_closest_monster, char_stream, player_stream)
            self.player_position = (await player_stream.next())['position']
            while True:
                target = await game.move_to_character(get_monster)
                if target is None and not self.invisible_monsters:
                    return
                distance_from_monster = 0
                while target and distance_from_monster < 90:
                    closest_monster_position = target['position']
                    distance_from_monster = game.distance_between_tiles_diagonal(self.player_position, closest_monster_position)
                    if distance_from_monster > 0:
                        direction_to_face = game.direction_from_positions(self.player_position, closest_monster_position)
                        await game.face_direction(direction_to_face, player_stream)
                    await game.swing_tool()
                    await asyncio.sleep(0.1)
                    target = await get_monster()

    async def get_closest_monster(self, char_stream, player_stream):
        chars = await char_stream.next()
        self.invisible_monsters = []
        visible_monsters = []
        for c in chars:
            if c['isMonster']:
                monster_list = self.invisible_monsters if c['isInvisible'] else visible_monsters
                monster_list.append(c)
        if not visible_monsters:
            if not self.invisible_monsters:
                raise RuntimeError('No monsters in current location')
            return
        if player_stream.has_value:
            self.player_position = player_stream.latest_value['position']
        server.log(visible_monsters)
        visible_monsters.sort(key=lambda x: game.distance_between_tiles_diagonal(self.player_position, (x['tileX'], x['tileY'])))
        closest_monster = visible_monsters[0]
        return closest_monster



async def cancel_active_objective():
    global active_objective
    if active_objective:
        await active_objective.run_task.cancel()
    active_objective = None


async def new_active_objective(new_objective: Objective):
    global active_objective
    global pending_objective
    pending_objective = new_objective
    await cancel_active_objective()
    if new_objective is pending_objective:
        pending_objective = None
        active_objective = new_objective
        await new_objective.wrap_run()


def objective_action(objective_cls, *args):
    format_args = lambda **kw: [objective_cls(*[kw.get(a, a) for a in args])]
    return server.AsyncFunction(new_active_objective, format_args=format_args)

def function_objective(async_fn, *args):
    format_args = lambda **kw: [FunctionObjective(async_fn, *[kw.get(a, a) for a in args])]
    return server.AsyncFunction(new_active_objective, format_args=format_args)

def format_args(args, **kw):
    formatted_args = []
    for a in args:
        try:
            formatted_arg = kw.get(a, a)
        except TypeError:
            formatted_arg = a
        formatted_args.append(formatted_arg)
    return formatted_args
