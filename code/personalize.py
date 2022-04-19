
import os
import threading

from talon import Context, registry, app, Module, settings
from .user_settings import get_lines_from_csv
class PersonalValueError(ValueError):
    pass

mod = Module()

mod.tag('personalization', desc='enable personalizations')

setting_enable_personalization = mod.setting(
    "enable_personalization",
    type=bool,
    default=False,
    desc="Whether to enable the personalizations defined by the CSV files in the settings folder.",
)

ctx = Context()
ctx.matches = r"""
tag: user.personalization
"""

# b,x = [(x[0],registry.contexts[x[1]]) for x in enumerate(registry.contexts)][152]
# y = [v for k,v in x.commands.items() if v.rule.rule == 'term <user.word>'][0]

personalization_mutex: threading.RLock = threading.RLock()
Personalize_Control_File_Name = "personalizations.csv"
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

    # this code has multiple event triggers, so make sure only one copy runs at a time
    # note: this mutex may not actually be needed, I put it in because I was seeing some odd
    # behavior which turned out to be https://github.com/talonvoice/talon/issues/451.
    with personalization_mutex:
        print(f'personalize.py - on_ready(): loading customizations from "{Personalize_Control_File_Name}"...')
        
        try:
            line_number = 0
            for action, target, *remainder in get_lines_from_csv(Personalize_Control_File_Name):
                line_number += 1

                if testing:
                    print(f'{Personalize_Control_File_Name}, at line {line_number} - {target, action, remainder}')
                    # print(f'{personalize_file_name}, at line {line_number} - {target in ctx.lists=}')
                    pass

                if not target in registry.lists:
                    print(f'{Personalize_Control_File_Name}, at line {line_number} - cannot redefine a list that does not exist, skipping: {target}')
                    continue

                file_name = None
                if len(remainder):
                    file_name = remainder[0]
                elif action.lower() != 'replace':
                    print(f'{Personalize_Control_File_Name}, at line {line_number} - missing file name for add or delete entry, skipping: {target}')
                    continue

                if target in ctx.lists.keys():
                    source = ctx.lists[target]
                else:
                    source = registry.lists[target][0]
                        
                value = {}
                if action.lower() == 'delete':
                    deletions = []
                    try:
                        for row in get_lines_from_csv(file_name):
                            if len(row) > 1:
                                print(f'{Personalize_Control_File_Name}, at line {line_number} - files containing deletions must have just one value per line, skipping entire file: {file_name}')
                                raise PersonalValueError()
                            deletions.append(row[0])
                    except FileNotFoundError:
                        print(f'{Personalize_Control_File_Name}, at line {line_number} - missing file for delete entry, skipping: {file_name}')
                        continue

                    # print(f'personalize_file_name - {deletions=}')

                    value = source.copy()
                    value = { k:v for k,v in source.items() if k not in deletions }

                elif action.lower() == 'add' or action.lower() == 'replace':
                    additions = {}
                    if file_name:
                        try:
                            for row in get_lines_from_csv(file_name):
                                if len(row) != 2:
                                    print(f'{Personalize_Control_File_Name}, at line {line_number} - files containing additions must have just two values per line, skipping entire file: {file_name}')
                                    raise PersonalValueError()
                                additions[ row[0] ] = row[1]
                        except FileNotFoundError:
                            print(f'{Personalize_Control_File_Name}, at line {line_number} - missing file for add or replace entry, skipping: {file_name}')
                            continue
                    
                    if action.lower() == 'add':
                        value = source.copy()
                        
                    value.update(additions)
                else:
                    print(f'{Personalize_Control_File_Name}, at line {line_number} - unknown action, skipping: {action}')
                    continue
                    
                # print(f'personalize_file_name - after {action.lower()}, {value=}')

                # do it to it
                ctx.lists[target] = value

                # if testing:
                    # print(f'AFTER - {target in ctx.lists=}')
                    # print(f'AFTER - {target in registry.lists=}')
        except FileNotFoundError:
            # nothing to do
            pass
        except PersonalValueError:
            # nothing to do
            pass

        # print(f'on_ready: {ctx.lists.keys()=}')
        # print(f'on_ready: {ctx.lists["user.punctuation"]=}')

        # if target in ctx.lists.keys() and not any([x in ctx.lists[target].keys() for x in deletions]):
        #     print(f'personalize.py - on_ready(): update succeeded')
        #     pass
        # else:
        #     print(f'personalize.py - on_ready(): update failed')
        #     pass
        
        # print(f'personalize.py - on_ready(): HERE - {ctx.lists["user.punctuation"].keys()}')

        # print(f'personalize.py: {"user.punctuation" in registry.lists=}')
        # print(f'personalize.py: {"user.punctuation" in ctx.lists.keys() and "pause" in ctx.lists["user.punctuation"].keys()=}')
        # print(f'personalize.py: {"user.special_key" in registry.lists and "clap" in registry.lists["user.special_key"][0].keys()=}')

app.register("ready", on_ready)