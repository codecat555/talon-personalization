
import os

from .user_settings import get_lines_from_csv, SETTINGS_DIR

from talon import Context, registry, app

class PersonalValueError(ValueError):
    pass

ctx = Context()
ctx.matches = r"""
tag: user.enable_personalizations
"""
# ctx.matches = r"""
# tag: user.enable_personalizations
# tag: user.enable_personalizations1
# """

# b,x = [(x[0],registry.contexts[x[1]]) for x in enumerate(registry.contexts)][152]
# y = [v for k,v in x.commands.items() if v.rule.rule == 'term <user.word>'][0]

# default_alphabet = "air bat cam drum each fine gust harp ice jane kick look made near odd pit quench red sun trap urge vest whale plex yip zip".split(' ')
# letters_string = "abcdefghijklmnopqrstuvwxyz"
# alphabet = dict(zip(default_alphabet, letters_string))

# supplemental_punctuation_words = {
#     'pause': ',',
#     'half pause': ';'
# }

# #
# supplemental_symbol_key_words = {
#     "lack": "[",
#     "rack": "]",
#     "close square": "]",
#     "lip": "(",
#     "rip": ")",
#     "close paren": ")",
#     "lace": "{",
#     "race": "}",
#     "close brace": "}",
#     "lang": "<",
#     "rang": ">",
#     "bar": "t"
# }

# supplemental_alternate_keys = {
#     "backspace": "backspace",
#     "wipe": "backspace",
#     "gobble": "delete",
#     "tabby": "tab",
#     "clap": "enter",
#     # gap conflicts with cap...so, let's replace cap
#     "gap": "space"
# }

# list_overrides = [
#     {
#         'target': 'user.letter',
#         'delete': 'ALL',
#         'add': alphabet
#     },
#     {
#         'target': 'user.punctuation',
#         'delete': [
#             'exclamation mark',
#         ],
#         'add': supplemental_punctuation_words
#     },
#     {
#         'target': 'user.symbol_key',
#         'delete': [],
#         'add': {
#             **supplemental_punctuation_words,
#             **supplemental_symbol_key_words
#         }
#     },
#     {
#         'target': 'user.special_key',
#         'delete': [],
#         'add': {
#             **supplemental_alternate_keys,
#         }
#     },
# ]

testing = True
def on_ready():

    personalize_file_name = "personalizations.csv"

    print(f'personalize.py - on_ready(): {ctx.path=}')

    print(f'personalize.py - on_ready(): loading customizations from "{personalize_file_name}"...')

    
    try:
        line_number = 0
        for action, target, *remainder in get_lines_from_csv(personalize_file_name):
            line_number += 1

            if testing:
                print(f'{personalize_file_name}, at line {line_number} - {target, action, remainder}')
                print(f'{personalize_file_name}, at line {line_number} - {target in ctx.lists=}')

            if not target in registry.lists:
                print(f'personalize_file_name - cannot redefine a list that does not exist, skipping: {target}')
                continue

            file_name = None
            if len(remainder):
                file_name = remainder[0]
            elif action.lower() != 'replace':
                print(f'{personalize_file_name}, at line {line_number} - missing file name for add or delete entry: {target}')
                continue

            if target in ctx.lists.keys():
                source = ctx.lists[target]
            else:
                source = registry.lists[target][0]
                    
            value = {}
            if action.lower() == 'delete':
                deletions = []
                try:
                    # for row in get_lines_from_csv(file_name, escapechar='\\'):
                    for row in get_lines_from_csv(file_name):
                        if len(row) > 1:
                            print(f'{personalize_file_name}, at line {line_number} - files containing deletions must have just one value per line, skipping entire file: {file_name}')
                            raise PersonalValueError()
                        deletions.append(row[0])
                except FileNotFoundError:
                    print(f'{personalize_file_name}, at line {line_number} - missing file for delete entry: {file_name}')
                    continue

                print(f'personalize_file_name - {deletions=}')

                value = source.copy()
                # value = { k:v for k,v in dict(registry.lists[target][0]).items() if k not in deletions }
                value = { k:v for k,v in source.items() if k not in deletions }

            elif action.lower() == 'add' or action.lower() == 'replace':
                additions = {}
                if file_name:
                    try:
                        # for row in get_lines_from_csv(file_name, escapechar='\\'):
                        for row in get_lines_from_csv(file_name):
                            if len(row) != 2:
                                print(f'{personalize_file_name}, at line {line_number} - files containing additions must have just two values per line, skipping entire file: {file_name}')
                                raise PersonalValueError()
                            additions[ row[0] ] = row[1]
                    except FileNotFoundError:
                        print(f'{personalize_file_name}, at line {line_number} - missing file for add or replace entry: {file_name}')
                        continue
                
                if action.lower() == 'add':
                    value = source.copy()
                    
                value.update(additions)
            else:
                raise ValueError(f'unknown action: {action}')
                
            print(f'personalize_file_name - after {action.lower()}, {value=}')

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

    if target in ctx.lists.keys() and not any([x in ctx.lists[target].keys() for x in deletions]):
        print(f'personalize.py - on_ready(): update succeeded')
    else:
        print(f'personalize.py - on_ready(): update failed')
    
    # print(f'personalize.py - on_ready(): HERE - {ctx.lists["user.punctuation"].keys()}')

    # print(f'personalize.py: {"user.punctuation" in registry.lists=}')
    print(f'personalize.py: {"user.punctuation" in ctx.lists.keys() and "pause" in ctx.lists["user.punctuation"].keys()=}')
    # print(f'personalize.py: {"user.special_key" in registry.lists and "clap" in registry.lists["user.special_key"][0].keys()=}')

app.register("ready", on_ready)