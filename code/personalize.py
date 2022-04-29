# This module provides a mechanism for overriding talon lists and commands via a set of csv files.
# 
# CONTROL FILE
# ------------
# There is a master csv file called 'control.csv' which indicates how the other files should
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
from pathlib import Path
import csv
import pprint

from talon import Context, registry, app, Module, settings, actions

class PersonalValueError(ValueError):
    pass

mod = Module()

setting_enable_personalization = mod.setting(
    "enable_personalization",
    type=bool,
    default=False,
    desc="Whether to enable the personalizations defined by the CSV files in the settings folder.",
)

personalization_tag = mod.tag('personalization', desc='enable personalizations')

mod.list("test_list_replacement", desc="a list for testing the personalization replacement feature")

ctx = Context()
ctx.matches = r"""
tag: user.personalization
"""

ctx.lists["user.test_list_replacement"] = {'one': 'blue', 'two': 'red', 'three': 'green'}

# b,x = [(x[0],registry.contexts[x[1]]) for x in enumerate(registry.contexts)][152]
# y = [v for k,v in x.commands.items() if v.rule.rule == 'term user.word>'][0]

class Personalizer():
    def __init__(self):
        self.personalization_mutex: threading.RLock = threading.RLock()
        self.command_add_disallowed_title = "Talon - ADD not allowed for commands"
        self.command_add_disallowed_notice = 'Command personalization: to add new commands, use a .talon file.'

        self.personalizations = {}

        self.control_file_name = 'control.csv'

        self.personal_csv_folder_name = 'csv'
        self.personal_root_folder_name = '_personalizations'
        # self.personal_root_path = actions.path.talon_user() / self.personal_root_folder_name
        self.personal_root_path = Path(__file__).parents[1] / self.personal_root_folder_name

        self.list_personalization_folder = 'list_personalization'
        self.command_personalization_folder = 'command_personalization'

        self.personal_list_control_file_name = os.path.join(self.list_personalization_folder, self.control_file_name)
        self.personal_command_control_file_name = os.path.join(self.command_personalization_folder, self.control_file_name)

        self.testing = True

        self.py_header = '# This file has been dynamically generated in order to override some of the definitions from context '
        self.talon_header = self.py_header

        self.tag_expression = f'tag: user.personalization'

    def load_personalization(self):
        if not settings.get('user.enable_personalization'):
            return

        # this code has multiple event triggers which may overlap. it's not clear how talon
        # handles that case, so use a mutex here to make sure only one copy runs at a time.
        #
        # note: this mutex may not actually be needed, I put it in because I was seeing multiple simultaneous
        # invocations of this code back when I was still using the stock CSV reader code...seems to have been
        # due to https://github.com/talonvoice/talon/issues/451.
        with self.personalization_mutex:
            self.load_list_personalizations()
            self.load_command_personalizations()
            self.generate_files()
   
    def load_list_personalizations(self):
        print(f'load_list_personalizations.py - on_ready(): loading customizations from "{self.personal_list_control_file_name}"...')
        new_context = None
        
        self.list_personalizations = {}
        try:
            line_number = 0
            for action, target_ctx_path, target_list, *remainder in self.get_lines_from_csv_untracked(self.personal_list_control_file_name):
                line_number += 1

                if self.testing:
                    print(f'{self.personal_list_control_file_name}, at line {line_number} - {action, target_ctx_path, target_list, remainder}')
                    # print(f'{personalize_file_name}, at line {line_number} - {target in ctx.lists=}')
                    pass

                if not target_ctx_path in registry.contexts:
                    print(f'{self.personal_list_control_file_name}, at line {line_number} - cannot redefine a context that does not exist, skipping: "{target_ctx_path}"')
                    continue
                
                if not target_list in registry.lists:
                    print(f'{self.personal_list_control_file_name}, at line {line_number} - cannot redefine a list that does not exist, skipping: "{target_list}"')
                    continue

                file_name = None
                if len(remainder):
                    file_name = os.path.join(self.list_personalization_folder, remainder[0])
                elif action.upper() != 'REPLACE':
                    print(f'{self.personal_list_control_file_name}, at line {line_number} - missing file name for add or delete entry, skipping: "{target_list}"')
                    continue

                if target_list in ctx.lists.keys():
                    source = ctx.lists[target_list]
                else:
                    source = registry.lists[target_list][0]
                        
                value = {}
                if action.upper() == 'DELETE':
                    deletions = []
                    try:
                        for row in self.get_lines_from_csv_untracked(file_name):
                            if len(row) > 1:
                                print(f'{self.personal_list_control_file_name}, at line {line_number} - files containing deletions must have just one value per line, skipping entire file: "{file_name}"')
                                raise PersonalValueError()
                            deletions.append(row[0])
                    except FileNotFoundError:
                        print(f'{self.personal_list_control_file_name}, at line {line_number} - missing file for delete entry, skipping: "{file_name}"')
                        continue

                    # print(f'personalize_file_name - {deletions=}')

                    value = source.copy()
                    value = { k:v for k,v in source.items() if k not in deletions }

                elif action.upper() == 'ADD' or action.upper() == 'REPLACE':
                    additions = {}
                    if file_name:  # some REPLACE entries may not have filenames, and that's okay
                        try:
                            for row in self.get_lines_from_csv_untracked(file_name):
                                if len(row) != 2:
                                    print(f'{self.personal_list_control_file_name}, at line {line_number} - files containing additions must have just two values per line, skipping entire file: "{file_name}"')
                                    raise PersonalValueError()
                                additions[ row[0] ] = row[1]
                        except FileNotFoundError:
                            print(f'{self.personal_list_control_file_name}, at line {line_number} - missing file for add or replace entry, skipping: "{file_name}"')
                            continue
                    
                    if action.upper() == 'ADD':
                        value = source.copy()
                        
                    value.update(additions)
                else:
                    print(f'{self.personal_list_control_file_name}, at line {line_number} - unknown action, skipping: "{action}"')
                    continue
                    
                # print(f'personalize_file_name - after {action.upper()}, {value=}')

                list_personalizations = self.get_list_personalizations(target_ctx_path)
                list_personalizations.update({target_list: value})

        except FileNotFoundError as e:
            # below check is necessary because the inner try blocks above do not catch this
            # error completely...something's odd about the way talon is handling these exceptions.
            if os.path.basename(e.filename) == self.personal_list_control_file_name:
                print(f'Setting  "{setting_enable_personalization.path}" is enabled, but personalization control file does not exist: "{self.personal_list_control_file_name}"')
        except PersonalValueError:
            # nothing to do
            pass

    def load_command_personalizations(self):
        print(f'load_command_personalizations(): loading customizations from "{self.personal_command_control_file_name}"...')
        
        self.command_personalizations = {}

        send_add_notification = False

        try:
            line_number = 0
            for action, target_ctx_path, file_name in self.get_lines_from_csv_untracked(self.personal_command_control_file_name):
                line_number += 1

                if self.testing:
                    # print(f'{self.personal_command_control_file_name}, at line {line_number} - {target, action, remainder}')
                    print(f'{self.personal_command_control_file_name}, at line {line_number} - {target_ctx_path, action, file_name}')
                    # print(f'{personalize_file_name}, at line {line_number} - {target in ctx.lists=}')
                    pass

                if not target_ctx_path in registry.contexts:
                    print(f'{self.personal_command_control_file_name}, at line {line_number} - cannot personalize commands in a context that does not exist, skipping: "{target_ctx_path}"')
                    continue

                file_path = os.path.join(self.command_personalization_folder, file_name)

                # WIP - not sure about this bit
                # if target in ctx.lists.keys():
                #     source = ctx.lists[target]
                # else:
                #     source = registry.lists[target][0]
                context = registry.contexts[target_ctx_path]

                commands = context.commands
                        
                value = {}
                if action.upper() == 'DELETE':
                    deletions = []
                    try:
                        for row in self.get_lines_from_csv_untracked(file_path):
                            if len(row) > 1:
                                print(f'{self.personal_command_control_file_name}, at line {line_number} - files containing deletions must have just one value per line, skipping entire file: "{file_path}"')
                                raise PersonalValueError()
                            deletions.append(row[0])
                    except FileNotFoundError:
                        print(f'{self.personal_command_control_file_name}, at line {line_number} - missing file for delete entry, skipping: "{file_path}"')
                        continue

                    # print(f'personalize_file_name - {deletions=}')
                    value = { k: 'skip()' for k in commands.keys() if k in deletions }
                    
                elif action.upper() == 'REPLACE':
                    additions = {}
                    try:
                        for row in self.get_lines_from_csv_untracked(file_path):
                            if len(row) != 2:
                                print(f'{self.personal_command_control_file_name}, at line {line_number} - files containing replacements must have just two values per line, skipping entire file: "{file_path}"')
                                raise PersonalValueError()
                            
                            target_command = row[0]
                            replacement_command = row[1]

                            try:
                                impl = commands[f'{target_command}'].target.code
                            except KeyError as e:
                                print(f'{self.personal_command_control_file_name}, at line {line_number} - cannot replace a command that does not exist, skipping: "{target_command}"')
                                continue
                            
                            print(f'HERE - {replacement_command}: {impl}')
                            additions[ target_command ] = 'skip()'
                            additions[ replacement_command ] = impl
                    except FileNotFoundError:
                        print(f'{self.personal_command_control_file_name}, at line {line_number} - missing file for add or replace entry, skipping: "{file_path}"')
                        continue
                        
                    value.update(additions)
                else:
                    if action.upper() == 'ADD':
                        send_add_notification = True
                        
                    print(f'{self.personal_command_control_file_name}, at line {line_number} - unknown action, skipping: "{action}"')
                    continue
                    
                # print(f'personalize_file_name - after {action.upper()}, {value=}')

                command_personalizations = self.get_command_personalizations(target_ctx_path)
                command_personalizations.update(value)

        except FileNotFoundError as e:
            # below check is necessary because the inner try blocks above do not catch this
            # error completely...something's odd about the way talon is handling these exceptions.
            print(f'personalize_file_name - {e.filename}')
            if os.path.basename(e.filename) == self.personal_command_control_file_name:
                print(f'Setting  "{setting_enable_personalization.path}" is enabled, but personalization control file does not exist: "{personal_command_control_file_name}"')
        except PersonalValueError:
            # nothing to do
            pass

        if send_add_notification:
            app.notify(
                title=self.command_add_disallowed_title,
                body=self.command_add_disallowed_notice
            )
            

    
    def add_tag_to_match_string(self, context_path: str, old_match_string: str, tag: str = None) -> str:
        if tag is None:
            tag = self.tag_expression

        new_match_string: str = old_match_string + tag

        print(f'{old_match_string=}, {new_match_string=}')
        return new_match_string

    def get_fs_path_prefix(self, context_path) -> Path:
        wip = context_path.split('.')

        filename_idx = -1
        if context_path.endswith('.talon'):
            filename_idx = -2

        filename = '.'.join(wip[filename_idx:])
            
        # leave off the last component, since this is a 'prefix' path
        wip = f'{os.path.sep}'.join(wip[1:filename_idx])
        # print(f'get_fs_path_prefix: got {context_path}, returning {wip, filename}')
        return wip, filename

    def write_py_header(self, f, context_path):
        print(f'{self.py_header}{context_path}', file=f)

    def write_py_context(self, f, context_path, match_string):
        print('from talon import Context', file=f)
        print('ctx = Context()', file=f)
        print(f'ctx.matches = """{match_string}"""\n', file=f)

    def write_talon_header(self, f, context_path):
        print(f'{self.talon_header}{context_path}', file=f)

    def write_talon_context(self, f, context_path, match_string):
        print(f'{match_string}\n-', file=f)
        
    def write_talon_tag_calls(self, f, context_path):
        for line in self.get_tag_calls(context_path):
            print(line, file=f, end='')
        print(file=f)

    def generate_files(self):
        print(f'personalize.py - generate_files(): writing customizations to "{self.personal_root_path}"...')
        current_files = []
        for ctx_path in self.personalizations:
            # print(f'generate_files: {ctx_path=}')

            filepath_prefix = self.get_personal_filepath_prefix(ctx_path)
            print(f'generate_files: {filepath_prefix=}')
            
            source_match_string = self.get_source_match_string(ctx_path)
            print(f'get_context_match_string: {ctx_path=}')
            print(f'get_context_match_string: {source_match_string=}')
            new_match_string = self.add_tag_to_match_string(ctx_path, source_match_string)
            print(f'get_context_match_string: {new_match_string=}')

            if not filepath_prefix in current_files:
                # truncate on open, if exists
                open_mode = 'w'
            else:
                # append, if exists
                open_mode = 'a'
            current_files.append(filepath_prefix)

            print(f'generate_files: {ctx_path=}, {new_match_string=}')

            if ctx_path.endswith('.talon'):
                command_personalizations = self.get_command_personalizations(ctx_path)
                filepath = str(filepath_prefix)
                with open(filepath, open_mode) as f:
                    self.write_talon_header(f, ctx_path)
                    
                    self.write_talon_context(f, ctx_path, new_match_string)
                    
                    self.write_talon_tag_calls(f, ctx_path)
                    
                    print(f'command_personalizations: {command_personalizations=}')
                    for personal_command, personal_impl in command_personalizations.items():
                        # print(f"NOW - {personal_command}: {personal_impl}\n")
                        print(f'{personal_command}:', file=f)
                        for line in personal_impl.split('\n'):
                            print(f'\t{line}', file=f)

            else:
                list_personalizations = self.get_list_personalizations(ctx_path)
                filepath = str(filepath_prefix) + '.py'
                print(f'personalize.py - generate_files(): writing customizations to "{filepath}"...')
                with open(filepath, open_mode) as f:
                    self.write_py_header(f, ctx_path)
                    self.write_py_context(f, ctx_path, new_match_string)
                    pp = pprint.PrettyPrinter(indent=4)
                    for list_name, list_value in list_personalizations.items():
                        print(f'ctx.lists["{list_name}"] = {pp.pformat(list_value)}\n', file=f)

    def get_source_match_string(self, context_path):
        source_match_string = None

        context_personalizations = self.get_personalizations(context_path)
        if 'source_context_match_string' in context_personalizations:
            source_match_string = context_personalizations['source_context_match_string']
        else:
            source_match_string, _ = self._get_matches_and_tags(context_path, context_personalizations)
            
        return source_match_string
    
    def get_tag_calls(self, context_path):
        tag_calls = None
        context_personalizations = self.get_personalizations(context_path)
        if 'tag_calls' in context_personalizations:
            tag_calls = context_personalizations['tag_calls']
        else:
            _, tag_calls = self._get_matches_and_tags(context_path, context_personalizations)
            
        return tag_calls

    def _get_matches_and_tags(self, context_path, context_personalizations):
        source_match_string, tag_calls = None, None
        if context_path.endswith('.talon'):
            # need to grab match string from the file
            source_match_string, tag_calls = self._parse_talon_file(context_path)
        else:
            context = self.get_source_context(context_path)
            source_match_string = context.matches
                
        context_personalizations['source_context_match_string'] = source_match_string
        context_personalizations['tag_calls'] = tag_calls
        
        return source_match_string, tag_calls

    def _parse_talon_file(self, context_path):
        path_prefix, filename = self.get_fs_path_prefix(context_path)
        filepath_prefix = os.path.join(actions.path.talon_user(), path_prefix, filename)
        
        source_match_string = ''
        tag_calls = []
        with open(filepath_prefix, 'r') as f:
            seen_dash = False
            for line in f:
                if seen_dash:
                    if line.strip().startswith('tag():'):
                        # filter out personalization tag here, or error...?
                        tag_calls.append(line)
                else:
                    if line.startswith('-'):
                        seen_dash = True
                    if line.lstrip().startswith('#'):
                        continue
                    else:
                        source_match_string += line
            else:
                # never found a '-' => no context header for this file
                source_match_string = ''
        
        return source_match_string, tag_calls

    def get_personal_filepath_prefix(self, ctx_path):
        path_prefix, filename = self.get_fs_path_prefix(ctx_path)
        path = self.personal_root_path / path_prefix
        if not os.path.exists(path):
            os.makedirs(path, mode=550, exist_ok=True)
            
        filepath_prefix = path / filename
        return filepath_prefix

    def get_personalizations(self, context_path: str):
        if not context_path in self.personalizations:
            self.personalizations[context_path] = {}

        return self.personalizations[context_path]

    def get_source_context(self, context_path: str):
        context_personalizations = self.get_personalizations(context_path)

        if not 'source_context' in context_personalizations:
            context_personalizations['source_context'] = registry.contexts[context_path]

        return context_personalizations['source_context']
        
    def get_list_personalizations(self, context_path: str):
        context_personalizations = self.get_personalizations(context_path)

        if not 'lists' in context_personalizations:
            context_personalizations['lists'] = {}
            
        return context_personalizations['lists']

    def get_command_personalizations(self, context_path: str):
        context_personalizations = self.get_personalizations(context_path)

        if not 'commands' in context_personalizations:
            context_personalizations['commands'] = {}
            
        return context_personalizations['commands']

    # added this while debugging an issue that turned out to be https://github.com/talonvoice/talon/issues/451.
    def get_lines_from_csv_untracked(self, filename: str, escapechar='\\'):
        """Retrieves contents of CSV file in settings dir, without tracking"""
        SETTINGS_DIR = Path(__file__).parents[1] / self.personal_root_folder_name

        path = SETTINGS_DIR / filename
        assert filename.endswith(".csv")

        # read via resource to take advantage of talon's
        # ability to reload this script for us when the resource changes
        rows = []
        with open(str(path), "r") as f:
            rows = list(csv.reader(f, escapechar=escapechar))

        print(f'returning {rows}')
        return rows

def on_ready():
    p.load_personalization()

    # catch updates
    settings.register("", refresh_settings)
    
def refresh_settings(setting_path, new_value):
        # print(f'refresh_settings() - {setting_path=}, {new_value=}')
        if setting_path == setting_enable_personalization.path:
            p.load_personalization()

p = Personalizer()

app.register("ready", on_ready)
