# Object classes from AP core, to represent an entire MultiWorld and this individual World that's part of it
from worlds.AutoWorld import World
from worlds.generic.Rules import add_rule
from copy import copy

from BaseClasses import MultiWorld
import json
import os
import pkgutil
import logging

# Object classes from Manual -- extending AP core -- representing items and locations that are used in generation
from ..Items import ManualItem
from ..Locations import ManualLocation

# Raw JSON data from the Manual apworld, respectively:
#          data/game.json, data/items.json, data/locations.json, data/regions.json
#
from ..Data import game_table, item_table, location_table, region_table
from .Options import RandomContent, Goal

# These helper methods allow you to determine if an option has been set, or what its value is, for any player in the multiworld
from ..Helpers import is_option_enabled, get_option_value

logger = logging.getLogger()
removedPlacedItems = {}
removedPlacedItemsCategory = {}
changedItemsCount = {}
OWMiscData = {}

########################################################################################
## Order of method calls when the world generates:
##    1. create_regions - Creates regions and locations
##    2. set_rules - Creates rules for accessing regions and locations
##    3. generate_basic - Creates the item pool and runs any place_item options
##    4. pre_fill - Creates the victory location
##
## The create_item method is used by plando and start_inventory settings to create an item from an item name.
## The fill_slot_data method will be used to send data to the Manual client for later use, like deathlink.
########################################################################################



# Called before regions and locations are created. Not clear why you'd want this, but it's here.
def before_create_regions(world: World, multiworld: MultiWorld, player: int):
    # Set version in yaml and log
    if 'version' in game_table:
        apworldversion = game_table['version']
        if apworldversion != "":
            multiworld.game_version[player].value = apworldversion
            if "versionTold" in OWMiscData:
                logger.info(f"player(s) uses {world.game} version: {apworldversion}")
                OWMiscData["versionTold"] = "yep :D"
        else:
            multiworld.game_version[player].value = "Unknown"
    else:
        multiworld.game_version[player].value = "Unknown"
    pass

# Called after regions and locations are created, in case you want to see or modify that information.
def after_create_regions(world: World, multiworld: MultiWorld, player: int):
    pass

# Called before rules for accessing regions and locations are created. Not clear why you'd want this, but it's here.
def before_set_rules(world: World, multiworld: MultiWorld, player: int):
    pass

# Called after rules for accessing regions and locations are created, in case you want to see or modify that information.
def after_set_rules(world: World, multiworld: MultiWorld, player: int):
    solanum = get_option_value(multiworld, player, "require_solanum") or False
    owlguy = get_option_value(multiworld, player, "require_prisoner") or False
    randomContent = get_option_value(multiworld, player, "randomized_content") or RandomContent.option_both
    goal = get_option_value(multiworld, player, "goal") or Goal.option_standard

#Victory Location access rules mod
#region
    if randomContent == RandomContent.option_base_game:
        owlguy = False
        if goal == Goal.option_prisoner: goal = Goal.default #imposible option
        elif goal == Goal.option_visit_all_archive: goal = Goal.default #imposible option
        elif goal == Goal.option_stuck_in_stranger: goal = Goal.default #imposible option
        elif goal == Goal.option_stuck_in_dream: goal = Goal.default #imposible option

    if goal == Goal.option_eye or (goal == Goal.option_standard and ( randomContent == RandomContent.option_both or randomContent == RandomContent.option_base_game)):
        victory_name = "FINAL > Get the Adv. warp core to the vessel and Warp to the Eye"
    elif goal == Goal.option_prisoner or (goal == Goal.option_standard and randomContent == RandomContent.option_dlc):
        victory_name = "94 - Communicate with the prisoner in the Subterranean Lake Dream"
    elif goal == Goal.option_visit_all_archive:
        victory_name = "9 - In a loop visit all 3 archive without getting caught"
    elif goal == Goal.option_ash_twin_project_break_spacetime:
        victory_name = "1 - Break Space-Time in the Ash Twin Project"
    elif goal == Goal.option_high_energy_lab_break_spacetime:
        victory_name = "1 - Break space time in the lab"
    elif goal == Goal.option_stuck_with_solanum:
        victory_name = "FINAL > Get the Adv. warp core and get stuck with Solanum on the Quantum Moon"
    elif goal == Goal.option_stuck_in_stranger:
        victory_name = "FINAL > Get the Adv. warp core to the Stranger and wait until Credits"
    elif goal == Goal.option_stuck_in_dream:
        victory_name = "FINAL > Get the Adv. warp core to the Stranger and die to get in the dreamworld"

    for location in multiworld.get_unfilled_locations(player):
        if location.name == victory_name:
            if solanum:
                add_rule(location,
                         lambda state: state.has("Seen Solanum", player))
            if owlguy:
                add_rule(location,
                         lambda state: state.has("Seen Prisoner", player))
#endregion

    pass

# The complete item pool prior to being set for generation is provided here, in case you want to make changes to it
def before_generate_basic(item_pool: list, world: World, multiworld: MultiWorld, player: int):
    solanum = get_option_value(multiworld, player, "require_solanum") or False
    owlguy = get_option_value(multiworld, player, "require_prisoner") or False
    reducedSpooks = get_option_value(multiworld, player, "reduced_spooks") or False
    do_place_item_category = get_option_value(multiworld, player, "do_place_item_category") or False
    randomContent = get_option_value(multiworld, player, "randomized_content") or RandomContent.option_both
    goal = get_option_value(multiworld, player, "goal") or Goal.option_standard

#Restore location placed items
#region
    if len(removedPlacedItems) > 0 or len(removedPlacedItemsCategory) > 0:
        readded_place_item_Count = 0
        locationstoCheck = {}
        locationstoCheck.update(removedPlacedItems)
        locationstoCheck.update(removedPlacedItemsCategory)
        for location in locationstoCheck:
            if location in world.location_names:
                worldlocation = world.location_name_to_location[location]
                if location in removedPlacedItemsCategory:
                    worldlocation["place_item_category"] = removedPlacedItemsCategory[location]
                    removedPlacedItemsCategory.pop(location)
                if location in removedPlacedItems:
                    worldlocation["place_item"] = removedPlacedItems[location]
                    removedPlacedItems.pop(location)
                if "place_item" in worldlocation or "place_item_category" in worldlocation:
                    readded_place_item_Count += 1
        if readded_place_item_Count > 0:
            multiworld.clear_location_cache()
            logger.debug(f"ReAdded placed item info to {readded_place_item_Count} locations.")
#endregion

# Personnal Item counts adjustment
#region
    item_counts= {}
    if randomContent == RandomContent.option_base_game:
        item_counts["forced Meditation"] = 2
        item_counts["Musical Instrument"] = 6
        item_counts["Ticket for (1) free death"] = 4

    elif randomContent == RandomContent.option_dlc:
        worldlocation = world.location_name_to_location["Get in ship for the first time"]
        removedPlacedItemsCategory[worldlocation.name] = copy(worldlocation["place_item_category"])
        worldlocation.pop("place_item_category", "")

        item_counts["forced Meditation"] = 3
        item_counts["Ticket for (1) free death"] = 5
    #if randomContent == RandomContent.option_base_game or randomContent == RandomContent.option_dlc:
        #if either only base game or only dlc
        #world.item_name_to_item["Ticket for (1) free death"]["count"] = 10

    for name, count in item_counts.items():
        checkedname = copy(name)
        # future change item name here
        items = []
        for item in item_pool:
            if item.player != player:
                continue
            if item.name == checkedname:
                items.append(item)
        if len(items) > count:
            for x in range(len(items) - count):
                item_pool.remove(items[x])
#endregion

    locations_to_be_removed = []

    if randomContent != RandomContent.option_both or reducedSpooks or not do_place_item_category :
        fname = os.path.join("..", "data", "dlc.json")
        dlc_data = json.loads(pkgutil.get_data(__name__, fname).decode())
        # THX Axxroy

    if not do_place_item_category:
        for location in list(dlc_data["no_place_item_category"]["locations"]):
            if location in world.location_name_to_location:
                worldlocation = world.location_name_to_location[location]
                if "place_item_category" in worldlocation:
                    removedPlacedItemsCategory[location] = copy(worldlocation["place_item_category"])
                    worldlocation.pop("place_item_category", "")
        multiworld.clear_location_cache()


    if randomContent != RandomContent.option_both:
        if randomContent == RandomContent.option_base_game:
            owlguy = False
            if goal == Goal.option_prisoner: goal = Goal.default #imposible option
            elif goal == Goal.option_visit_all_archive: goal = Goal.default #imposible option
            elif goal == Goal.option_stuck_in_stranger: goal = Goal.default #imposible option
            elif goal == Goal.option_stuck_in_dream: goal = Goal.default #imposible option
            reducedSpooks = False
            message = "Base game"
            for item in list(item_pool):
                if item.name in dlc_data["echoes"]["items"]:
                    item_pool.remove(item)
            locations_to_be_removed += dlc_data["echoes"]["locations"]
        elif randomContent == RandomContent.option_dlc:
            message = "DLC"
            valid_items = dlc_data["echoes"]["items"] + dlc_data["both"]["items"]
            valid_locations = dlc_data["echoes"]["locations"] + dlc_data["both"]["locations"]
            if goal == Goal.option_eye:
                valid_items += dlc_data["victory_eye"]["items"]
                valid_locations += dlc_data["victory_eye"]["locations"]
                message += " + Eye"
            elif goal == Goal.option_ash_twin_project_break_spacetime:
                valid_items += dlc_data["victory_ash_twin_project_break_spacetime"]["items"]
                valid_locations += dlc_data["victory_ash_twin_project_break_spacetime"]["locations"]
                message += " + Ash Twin project"
            elif goal == Goal.option_high_energy_lab_break_spacetime:
                valid_items += dlc_data["victory_high_energy_lab_break_spacetime"]["items"]
                valid_locations += dlc_data["victory_high_energy_lab_break_spacetime"]["locations"]
                message += " + High Energy Lab"
            elif goal == Goal.option_stuck_in_stranger or goal == Goal.option_stuck_in_dream:
                valid_items +=  dlc_data["need_warpdrive"]["items"]
                valid_locations += dlc_data["need_warpdrive"]["locations"]
                message += " + Adv. warp core"
            elif goal == Goal.option_stuck_with_solanum:
                valid_items +=  dlc_data["need_warpdrive"]["items"] + dlc_data["require_solanum"]["items"]
                valid_locations += dlc_data["need_warpdrive"]["locations"] + dlc_data["require_solanum"]["locations"]
                message += " + Adv. warp core + Solanum"
            if solanum and goal != Goal.option_stuck_with_solanum:
                valid_items += dlc_data["require_solanum"]["items"]
                valid_locations += dlc_data["require_solanum"]["locations"]
                message += " + Solanum"

            for item in list(item_pool):
                if item.name not in valid_items:
                    item_pool.remove(item)

            for location in list(world.location_name_to_location):
                if location not in valid_locations:
                    locations_to_be_removed.append(location)

    else:
        message = "Both"
    #logger.info(message)

    if goal != Goal.option_stuck_with_solanum:
        locations_to_be_removed.append("FINAL > Get the Adv. warp core and get stuck with Solanum on the Quantum Moon")
    if goal != Goal.option_stuck_in_stranger:
        locations_to_be_removed.append("FINAL > Get the Adv. warp core to the Stranger and wait until Credits")
    if goal != Goal.option_stuck_in_dream:
        locations_to_be_removed.append("FINAL > Get the Adv. warp core to the Stranger and die to get in the dreamworld")

    if reducedSpooks:
        locations_to_be_removed += dlc_data["reduce_spooks"]["locations"]
        #do stuff to reduce spook like change requires of some locations

    if (goal != Goal.option_eye and not (goal == Goal.option_standard and (randomContent != RandomContent.option_dlc))):
        locations_to_be_removed.append("FINAL > Get the Adv. warp core to the vessel and Warp to the Eye")

    local_valid_locations = copy(world.location_name_to_location)
    removedlocCount = 1 #victory included
    if len(locations_to_be_removed) > 0:
        for region in multiworld.regions:
            if region.player != player:
                continue
            for location in list(region.locations):
                if location.name in locations_to_be_removed:
                    worldlocation = world.location_name_to_location[location.name]
                    if 'place_item' in worldlocation:
                        removedPlacedItems[location.name] = copy(worldlocation["place_item"])
                        worldlocation.pop("place_item", "")
                    if'place_item_category' in worldlocation:
                        removedPlacedItemsCategory[location.name] = copy(worldlocation["place_item_category"])
                        worldlocation.pop("place_item_category", "")
                    region.locations.remove(location)
                    local_valid_locations.pop(location.name, "")
                    removedlocCount += 1
        multiworld.clear_location_cache()

    logger.info(f"{world.game}:{player}:({message}) {len(item_pool)} items | {len(world.location_names) - removedlocCount} locations")

#Placing Victory item in location
#region
    VictoryInfoToAdd = ""
    if solanum: VictoryInfoToAdd += " + 'Seen Solanum'"
    if owlguy: VictoryInfoToAdd += " + 'Seen Prisoner'"

    if goal == Goal.option_eye or (goal == Goal.option_standard and ( randomContent == RandomContent.option_both or randomContent == RandomContent.option_base_game)):
        victory_name = "FINAL > Get the Adv. warp core to the vessel and Warp to the Eye"
        victory_base_message = "Eye"
    elif goal == Goal.option_prisoner or (goal == Goal.option_standard and randomContent == RandomContent.option_dlc):
        victory_name = "94 - Communicate with the prisoner in the Subterranean Lake Dream"
        victory_base_message = "Prisoner"
    elif goal == Goal.option_visit_all_archive:
        victory_name = "9 - In a loop visit all 3 archive without getting caught"
        victory_base_message = "Visit all archive"
    elif goal == Goal.option_ash_twin_project_break_spacetime:
        victory_name = "1 - Break Space-Time in the Ash Twin Project"
        victory_base_message = "Ash Twin Project"
    elif goal == Goal.option_high_energy_lab_break_spacetime:
        victory_name = "1 - Break space time in the lab"
        victory_base_message = "High Energy Lab"
    elif goal == Goal.option_stuck_with_solanum:
        victory_name = "FINAL > Get the Adv. warp core and get stuck with Solanum on the Quantum Moon"
        victory_base_message = "Stuck with Solanum"
    elif goal == Goal.option_stuck_in_stranger:
        victory_name = "FINAL > Get the Adv. warp core to the Stranger and wait until Credits"
        victory_base_message = "Stuck in Stranger"
    elif goal == Goal.option_stuck_in_dream:
        victory_name = "FINAL > Get the Adv. warp core to the Stranger and die to get in the dreamworld"
        victory_base_message = "Stuck in Dreamworld"
    victory_message = victory_base_message + VictoryInfoToAdd

    for item in item_pool:
        if item.player != player:
            continue
        if item.name == "Victory Token":
            victory_item = item
            break
    for location in multiworld.get_unfilled_locations(player):
        if location.name == victory_name:
            location.place_locked_item(victory_item)
    item_pool.remove(victory_item)

    logger.info(f'Set the player {multiworld.get_player_name(player)} Victory rules to {victory_message}')
#endregion

    return item_pool

# This method is run at the very end of pre-generation, once the place_item options have been handled and before AP generation occurs
def after_generate_basic(world: World, multiworld: MultiWorld, player: int):
    pass

# This method is called before the victory location has the victory event placed and locked
def before_pre_fill(world: World, multiworld: MultiWorld, player: int):
    pass

# This method is called after the victory location has the victory event placed and locked
def after_pre_fill(world: World, multiworld: MultiWorld, player: int):
    pass

# The item name to create is provided before the item is created, in case you want to make changes to it
def before_create_item(item_name: str, world: World, multiworld: MultiWorld, player: int) -> str:
    return item_name

# The item that was created is provided after creation, in case you want to modify the item
def after_create_item(item: ManualItem, world: World, multiworld: MultiWorld, player: int) -> ManualItem:
    return item

# This is called before slot data is set and provides an empty dict ({}), in case you want to modify it before Manual does
def before_fill_slot_data(slot_data: dict, world: World, multiworld: MultiWorld, player: int) -> dict:
    return slot_data

# This is called after slot data is set and provides the slot data at the time, in case you want to check and modify it after Manual is done with it
def after_fill_slot_data(slot_data: dict, world: World, multiworld: MultiWorld, player: int) -> dict:
    return slot_data