"""
Command-module loader for Kaldi.

This script is based on 'dfly-loader-wsr.py' written by Christo Butcher and
has been adapted to work with the Kaldi engine instead.

This script can be used to look for Dragonfly command-modules for use with
the Kaldi engine. It scans the directory it's in and loads any ``_*.py`` it
finds.
"""


# TODO Have a simple GUI for pausing, resuming, cancelling and stopping
# recognition, etc

import os.path
import os
import threading
import time
import logging
import sys

from dragonfly import RecognitionObserver, get_engine, AppContext
from dragonfly.log import setup_log
from srabuilder import sleep, environment
import srabuilder

import stardew, new_game_menu, shop_menu, container_menu, title_menu, load_game_menu, dialogue_menu, no_menu, any_menu, shipping_bin_menu, carpenter_menu, billboard_menu, geode_menu, museum_menu
import letter_viewer_menu, quest_log_menu, animal_query_menu
from game_menu import game_menu, crafting_page, inventory_page, exit_page


# --------------------------------------------------------------------------
# Simple recognition observer class.


class Observer(RecognitionObserver):
    def on_begin(self):
        print("Speech started.")

    def on_recognition(self, words):
        print("Recognized:", " ".join(words))

    def on_failure(self):
        print("Sorry, what was that?")


def command_line_loop(engine):
    while True:
        user_input = input("> ")
        if user_input:
            time.sleep(4)
            try:
                engine.mimic(user_input)
            except Exception as e:
                print(e)


# --------------------------------------------------------------------------
# Main event driving loop.


def main(args):
    logging.basicConfig(level=logging.INFO)
    engine = srabuilder.setup_engine(silence_timeout=275)

    # Register a recognition observer
    observer = Observer()
    observer.register()

    sleep.load_sleep_wake_grammar(True)
    startdew_context = AppContext(title="stardew")
    map_contexts_to_builder = {
        (startdew_context,): stardew.rule_builder(),
    }
    srabuilder.load_environment_grammars(map_contexts_to_builder)
    new_game_menu.load_grammar()
    shop_menu.load_grammar()
    container_menu.load_grammar()
    game_menu.load_grammar()
    crafting_page.load_grammar()
    inventory_page.load_grammar()
    exit_page.load_grammar()
    title_menu.load_grammar()   
    load_game_menu.load_grammar()   
    dialogue_menu.load_grammar()   
    no_menu.load_grammar()   
    any_menu.load_grammar()
    shipping_bin_menu.load_grammar()
    carpenter_menu.load_grammar()
    billboard_menu.load_grammar()
    geode_menu.load_grammar()
    museum_menu.load_grammar()
    letter_viewer_menu.load_grammar()
    quest_log_menu.load_grammar()
    animal_query_menu.load_grammar()

    # threading.Thread(target=command_line_loop, args=(engine,), daemon=True).start()
    srabuilder.run_engine()


if __name__ == "__main__":
    main(sys.argv[1:])
