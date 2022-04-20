
# this module provides a mechanism for overriding talon lists via a set of csv files located
# in a sub-folder of the settings folder - 'settings/list_personalization'.
# 
# CONTROL FILE
# ------------
# there is a master csv file called 'control.csv' which indicates how the other files should
# be used. It's format is:
#
#        action,talon list name,CSV file name
#
# The first field, action, may be ADD, DELETE, or REPLACE.
#
#     ADD - the CSV file entries should be added to the indicated list.
#  DELETE - the CSV file entries should be deleted from the indicated list.
# REPLACE - the indicated list should be completely replaced by the CSV file entries,
#           or by nothing if no CSV file is given.
#
# Note: the CSV file name field is optional for the REPLACE action, in which case the
# indicated list will simply be replaced with nothing.
#
#
# CSV FILE FORMAT - GENERAL
# -------------------------
# Nothing fancy, just basic comma-separated values. Commas in the data can be escaped
# using a backslash prefix.
#
#
# CSV FILE FORMAT - FOR DELETE ACTION
# -----------------------------------
# One item per line, indicating which keys should be removed from the given list.
#
#
# CSV FILE FORMAT - FOR ADD/REPLACE ACTIONS
# -----------------------------------------
# Two items per line, separated by a single comma. The first value is the key, and the
# second the value.

import os
import threading

from talon import Context, registry, app, Module, settings
from .user_settings import get_lines_from_csv
class PersonalValueError(ValueError):
    pass

mod = Module()

setting_enable_personalization = mod.setting(
    "enable_personalization",
    type=bool,
    default=False,
    desc="Whether to enable the personalizations defined by the CSV files in the settings folder.",
)

mod.tag('personalization', desc='enable personalizations')

mod.list("test_list_replacement", desc="a list for testing the personalization replacement feature")

ctx = Context()
ctx.matches = r"""
tag: user.personalization
"""

ctx.lists["user.test_list_replacement"] = {'one': 'blue', 'two': 'red', 'three': 'green'}

# b,x = [(x[0],registry.contexts[x[1]]) for x in enumerate(registry.contexts)][152]
# y = [v for k,v in x.commands.items() if v.rule.rule == 'term user.word>'][0]

personalization_mutex: threading.RLock = threading.RLock()

list_personalization_folder = 'list_personalization'
personalize_control_file_name = os.path.join(list_personalization_folder, 'control.csv')
testing = True

def refresh_settings(setting_path, new_value):
    # print(f'refresh_settings() - {setting_path=}, {new_value=}')
    if setting_path == setting_enable_personalization.path:
        load_personalization()

def on_ready():
    load_personalization()

    # catch updates
    settings.register("", refresh_settings)

def load_personalization():
    if not settings.get('user.enable_personalization'):
        return

    # this code has multiple event triggers which may overlap. it's not clear how talon
    # handles that case, so use a mutex here to make sure only one copy runs at a time.
    #
    # note: this mutex may not actually be needed, I put it in because I was multiple simultaneous
    # invocations of this code, which seem to be due to https://github.com/talonvoice/talon/issues/451.
    with personalization_mutex:
        print(f'personalize.py - on_ready(): loading customizations from "{personalize_control_file_name}"...')
        
        try:
            line_number = 0
            for action, target, *remainder in get_lines_from_csv(personalize_control_file_name):
                line_number += 1

                if testing:
                    print(f'{personalize_control_file_name}, at line {line_number} - {target, action, remainder}')
                    # print(f'{personalize_file_name}, at line {line_number} - {target in ctx.lists=}')
                    pass

                if not target in registry.lists:
                    print(f'{personalize_control_file_name}, at line {line_number} - cannot redefine a list that does not exist, skipping: {target}')
                    continue

                file_name = None
                if len(remainder):
                    file_name = os.path.join(list_personalization_folder, remainder[0])
                elif action.upper() != 'REPLACE':
                    print(f'{personalize_control_file_name}, at line {line_number} - missing file name for add or delete entry, skipping: {target}')
                    continue

                if target in ctx.lists.keys():
                    source = ctx.lists[target]
                else:
                    source = registry.lists[target][0]
                        
                value = {}
                if action.upper() == 'DELETE':
                    deletions = []
                    try:
                        for row in get_lines_from_csv(file_name):
                            if len(row) > 1:
                                print(f'{personalize_control_file_name}, at line {line_number} - files containing deletions must have just one value per line, skipping entire file: {file_name}')
                                raise PersonalValueError()
                            deletions.append(row[0])
                    except FileNotFoundError:
                        print(f'{personalize_control_file_name}, at line {line_number} - missing file for delete entry, skipping: {file_name}')
                        continue

                    # print(f'personalize_file_name - {deletions=}')

                    value = source.copy()
                    value = { k:v for k,v in source.items() if k not in deletions }

                elif action.upper() == 'ADD' or action.upper() == 'REPLACE':
                    additions = {}
                    if file_name:  # some REPLACE entries may not have filenames, and that's okay
                        try:
                            for row in get_lines_from_csv(file_name):
                                if len(row) != 2:
                                    print(f'{personalize_control_file_name}, at line {line_number} - files containing additions must have just two values per line, skipping entire file: {file_name}')
                                    raise PersonalValueError()
                                additions[ row[0] ] = row[1]
                        except FileNotFoundError:
                            print(f'{personalize_control_file_name}, at line {line_number} - missing file for add or replace entry, skipping: {file_name}')
                            continue
                    
                    if action.upper() == 'ADD':
                        value = source.copy()
                        
                    value.update(additions)
                else:
                    print(f'{personalize_control_file_name}, at line {line_number} - unknown action, skipping: {action}')
                    continue
                    
                # print(f'personalize_file_name - after {action.upper()}, {value=}')

                # do it to it
                ctx.lists[target] = value

        except FileNotFoundError as e:
            # below check is necessary because the inner try blocks above do not catch this
            # error completely...something's odd about the way talon is handling these exceptions.
            if os.path.basename(e.filename) == personalize_control_file_name:
                print(f'Setting  "{setting_enable_personalization.path}" is enabled, but personalization control file does not exist: {personalize_control_file_name}')
        except PersonalValueError:
            # nothing to do
            pass

app.register("ready", on_ready)
