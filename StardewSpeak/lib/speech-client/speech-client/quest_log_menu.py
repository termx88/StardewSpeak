import game, server, menu_utils, df_utils, items
from srabuilder import rules
import functools
import dragonfly as df

QUEST_LOG_MENU = "questLogMenu"


async def focus_quest(menu, n):
    quest = menu["questLogButtons"][n]
    await menu_utils.click_component(quest)


mapping = {
    "prior": menu_utils.simple_click("backButton"),
    "next": menu_utils.simple_click("forwardButton"),
    "[quest] cancel": menu_utils.simple_click("cancelQuestButton"),
    "scree sauce": menu_utils.simple_click("upArrow"),
    "scree dunce": menu_utils.simple_click("downArrow"),
    "((reward | rewards) [collect] | shock | collect)": menu_utils.simple_click("rewardBox"),
    "(item | quest) <positive_index>": df_utils.async_action(
        focus_quest, "positive_index"
    ),
}


def load_grammar():
    extras = [df_utils.positive_index]
    grammar = menu_utils.build_menu_grammar(mapping, QUEST_LOG_MENU, extras=extras)
    grammar.load()
