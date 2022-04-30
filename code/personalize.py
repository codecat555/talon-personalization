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
from threading import RLock
from pathlib import Path
import csv
import pprint
from shutil import rmtree
from typing import Any, List, Dict, Union

from talon import Context, registry, app, Module, settings, actions

class PersonalValueError(ValueError):
    pass

class Personalizer():
    def __init__(self):
        self.personalization_mutex: RLock = RLock()

        self.mod = Module()
        self.enable_setting = self.mod.setting(
            "enable_personalization",
            type=bool,
            default=False,
            desc="Whether to enable the personalizations defined by the CSV files in the settings folder.",
        )

        self.personalization_tag_name = 'personalization'
        self.personalization_tag_name_qualified = 'user.' + self.personalization_tag_name
        self.personalization_tag = self.mod.tag(self.personalization_tag_name, desc='enable personalizations')

        self.ctx = Context()
        self.ctx.matches = f'tag: {self.personalization_tag_name_qualified}'
        
        self.personalizations = {}

        self.control_file_name = 'control.csv'

        self.personal_csv_folder_name = 'csv'
        self.personal_csv_folder = Path(__file__).parents[1] / self.personal_csv_folder_name
        
        self.personal_folder_name = '_personalizations'
        self.personal_folder_path = Path(__file__).parents[1] / self.personal_folder_name

        self.personal_list_folder_name = 'list_personalization'
        self.personal_list_control_file_name = os.path.join(self.personal_list_folder_name, self.control_file_name)

        self.personal_command_folder_name = 'command_personalization'
        self.personal_command_control_file_name = os.path.join(self.personal_command_folder_name, self.control_file_name)
        
        self.command_add_disallowed_title = "Talon - ADD not allowed for commands"
        self.command_add_disallowed_notice = 'Command personalization: to add new commands, use a .talon file.'

        self.testing = True
  
        self.py_header = r"""
# DO NOT MODIFY THIS FILE - it has been dynamically generated in order to override some of
# the definitions from context '{}'.
#
# To customize this file, copy it to a different location outside the '{}'
# folder. Be sure you understand how Talon context matching works, so you can avoid conflicts
# with this file. If you do that, you may also want to remove the control.csv line that creates
# this file.
#"""
        self.talon_header = self.py_header

        self.tag_expression = f'tag: user.personalization'

    def refresh_settings(self, target_ctx_path: str, new_value: Any) -> None:
        # print(f'refresh_settings() - {target_ctx_path=}, {new_value=}')
        if target_ctx_path == self.enable_setting.path:
            if new_value:
                self.load_personalization()
            else:
                # instead, we could just disable the tag here...
                self.unload_personalization()

    def unload_personalization(self) -> None:
        with self.personalization_mutex:
            self.personalizations = {}
            if os.path.exists(self.personal_folder_path):
                rmtree(self.personal_folder_path)

    def load_personalization(self) -> None:
        # this code may have multiple event triggers which may overlap. it's not clear how talon
        # handles that case, so we use a mutex here to make sure only one copy runs at a time.
        #
        # note: this mutex may not actually be needed, I put it in because I was seeing multiple simultaneous
        # invocations of this code back when I was still using the stock CSV reader code...that behavior seems
        # to have been due to https://github.com/talonvoice/talon/issues/451.
        with self.personalization_mutex:
            if settings.get('user.enable_personalization'):
                self.ctx.tags = [self.personalization_tag_name_qualified]
                self.load_list_personalizations()
                self.load_command_personalizations()
                self.generate_files()
            else:
                self.ctx.tags = []
                return
   
    def load_list_personalizations(self) -> None:
        print(f'load_list_personalizations.py - on_ready(): loading customizations from "{self.personal_list_control_file_name}"...')
        
        self.list_personalizations = {}
        try:
            line_number = 0
            for action, target_ctx_path, target_list, *remainder in self.get_lines_from_csv_untracked(self.personal_list_control_file_name):
                line_number += 1

                if self.testing:
                    print(f'{self.personal_list_control_file_name}, at line {line_number} - {action, target_ctx_path, target_list, remainder}')
                    # print(f'{personalize_file_name}, at line {line_number} - {target in ctx.lists=}')

                if not target_ctx_path in registry.contexts:
                    print(f'{self.personal_list_control_file_name}, at line {line_number} - cannot redefine a context that does not exist, skipping: "{target_ctx_path}"')
                    continue
                
                if not target_list in registry.lists:
                    print(f'{self.personal_list_control_file_name}, at line {line_number} - cannot redefine a list that does not exist, skipping: "{target_list}"')
                    continue

                file_name = None
                if len(remainder):
                    file_name = os.path.join(self.personal_list_folder_name, remainder[0])
                elif action.upper() != 'REPLACE':
                    print(f'{self.personal_list_control_file_name}, at line {line_number} - missing file name for add or delete entry, skipping: "{target_list}"')
                    continue

                # WIP - need to review this, is it correct?
                if target_list in self.ctx.lists.keys():
                    print(f'WE DO ACTUALLY GET HERE SOMETIMES')
                    source = self.ctx.lists[target_list]
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
                print(f'Setting  "{self.setting_enable_personalization.path}" is enabled, but personalization control file does not exist: "{self.personal_list_control_file_name}"')
        except PersonalValueError:
            # nothing to do
            pass

    def load_command_personalizations(self) -> None:
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

                if not target_ctx_path in registry.contexts:
                    print(f'{self.personal_command_control_file_name}, at line {line_number} - cannot personalize commands in a context that does not exist, skipping: "{target_ctx_path}"')
                    continue

                file_path = os.path.join(self.personal_command_folder_name, file_name)

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
                print(f'Setting  "{self.setting_enable_personalization.path}" is enabled, but personalization control file does not exist: "{self.personal_command_control_file_name}"')
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

    def get_fs_path_prefix(self, context_path: str) -> Path:
        wip = context_path.split('.')

        filename_idx = -1
        if context_path.endswith('.talon'):
            filename_idx = -2

        filename = '.'.join(wip[filename_idx:])
            
        # leave off the last component, since this is a 'prefix' path
        wip = f'{os.path.sep}'.join(wip[1:filename_idx])
        # print(f'get_fs_path_prefix: got {context_path}, returning {wip, filename}')
        return wip, filename

    def write_py_header(self, f, context_path: str) -> None:
        header = self.py_header.format(context_path, self.personal_folder_name)
        # print(f'{self.py_header}{context_path}', file=f)
        print(header, file=f)

    def write_py_context(self, f, match_string: str) -> None:
        print('from talon import Context', file=f)
        print('ctx = Context()', file=f)
        print(f'ctx.matches = """{match_string}"""\n', file=f)

    def write_talon_header(self, f, context_path: str) -> None:
        header = self.talon_header.format(context_path, self.personal_folder_name)
        print(header, file=f)

    def write_talon_context(self, f, match_string: str) -> None:
        print(f'{match_string}\n-', file=f)
        
    def write_talon_tag_calls(self, f, context_path: str) -> None:
        for line in self.get_tag_calls(context_path):
            print(line, file=f, end='')
        print(file=f)

    def generate_files(self) -> None:
        print(f'generate_files - generate_files(): writing customizations to "{self.personal_folder_path}"...')
        current_files = []
        
        self.unload_personalization()
            
        for ctx_path in self.personalizations:
            # print(f'generate_files: {ctx_path=}')

            filepath_prefix = self.get_personal_filepath_prefix(ctx_path)
            print(f'generate_files: {filepath_prefix=}')
            
            source_match_string = self.get_source_match_string(ctx_path)
            print(f'generate_files: {ctx_path=}')
            print(f'generate_files: {source_match_string=}')
            new_match_string = self.add_tag_to_match_string(ctx_path, source_match_string)
            print(f'generate_files: {new_match_string=}')

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
                    
                    self.write_talon_context(f, new_match_string)
                    
                    self.write_talon_tag_calls(f, ctx_path)
                    
                    print(f'generate_files: {command_personalizations=}')
                    for personal_command, personal_impl in command_personalizations.items():
                        print(f'{personal_command}:', file=f)
                        for line in personal_impl.split('\n'):
                            print(f'\t{line}', file=f)

            else:
                list_personalizations = self.get_list_personalizations(ctx_path)
                filepath = str(filepath_prefix) + '.py'
                print(f'generate_files - generate_files(): writing customizations to "{filepath}"...')
                with open(filepath, open_mode) as f:
                    self.write_py_header(f, ctx_path)
                    self.write_py_context(f, new_match_string)
                    pp = pprint.PrettyPrinter(indent=4)
                    for list_name, list_value in list_personalizations.items():
                        print(f'generate_files - ctx.lists["{list_name}"] = {pp.pformat(list_value)}\n', file=f)

    def get_source_match_string(self, context_path: str) -> str:
        source_match_string = None

        context_personalizations = self.get_personalizations(context_path)
        if 'source_context_match_string' in context_personalizations:
            source_match_string = context_personalizations['source_context_match_string']
        else:
            source_match_string, _ = self._get_matches_and_tags(context_path, context_personalizations)
            
        return source_match_string
    
    def get_tag_calls(self, context_path: str) -> List[str]:
        tag_calls = None
        context_personalizations = self.get_personalizations(context_path)
        if 'tag_calls' in context_personalizations:
            tag_calls = context_personalizations['tag_calls']
        else:
            _, tag_calls = self._get_matches_and_tags(context_path, context_personalizations)
            
        return tag_calls

    def _get_matches_and_tags(self, context_path: str, context_personalizations: Dict) -> Union[str, List[str]]:
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

    def _parse_talon_file(self, context_path: str) -> Union[str, List[str]]:
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

    def get_personal_filepath_prefix(self, context_path: str) -> Path:
        path_prefix, filename = self.get_fs_path_prefix(context_path)
        path = self.personal_folder_path / path_prefix
        if not os.path.exists(path):
            os.makedirs(path, mode=550, exist_ok=True)
            
        filepath_prefix = path / filename
        return filepath_prefix

    def get_personalizations(self, context_path: str) -> Dict:
        if not context_path in self.personalizations:
            self.personalizations[context_path] = {}

        return self.personalizations[context_path]

    def get_source_context(self, context_path: str) -> Dict:
        context_personalizations = self.get_personalizations(context_path)

        if not 'source_context' in context_personalizations:
            context_personalizations['source_context'] = registry.contexts[context_path]

        return context_personalizations['source_context']
        
    def get_list_personalizations(self, context_path: str) -> Dict:
        context_personalizations = self.get_personalizations(context_path)

        if not 'lists' in context_personalizations:
            context_personalizations['lists'] = {}
            
        return context_personalizations['lists']

    def get_command_personalizations(self, context_path: str) -> Dict:
        context_personalizations = self.get_personalizations(context_path)

        if not 'commands' in context_personalizations:
            context_personalizations['commands'] = {}
            
        return context_personalizations['commands']

    # added this while debugging an issue that turned out to be https://github.com/talonvoice/talon/issues/451.
    def get_lines_from_csv_untracked(self, filename: str, escapechar: str ='\\') -> List[str]:
        """Retrieves contents of CSV file in settings dir, without tracking"""
        
        csv_folder = self.personal_csv_folder

        path = csv_folder / filename
        assert filename.endswith(".csv")
        rows = []
        with open(str(path), "r") as f:
            rows = list(csv.reader(f, escapechar=escapechar))

        print(f'returning {rows}')
        return rows

def on_ready() -> None:
    personalizer.load_personalization()

    # catch updates
    settings.register("", personalizer.refresh_settings)
    
personalizer = Personalizer()

app.register("ready", on_ready)
