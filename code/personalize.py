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
from typing import Any, List, Dict, Union, Tuple, Callable

from talon import Context, registry, app, Module, settings, actions, fs

class LoadError(Exception):
    pass

class ItemCountError(Exception):
    pass

class FilenameError(Exception):
    pass

class Personalizer():
    
    def __init__(self):
        # this code has multiple event triggers which may overlap. so, we use a mutex to make sure
        # only one copy runs at a time.
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
        
        # self.deleted_context_title = "Talon - personalization source file disappeared"
        # self.deleted_context_notice = 'Personalization: personalizations have been invalidated because the source file has disappeared.'

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

    # def __del__(self) -> None:
    #     print(f'__del__: UNLOADING PERSONALIZATIONS ON OBJECT DESTRUCTION')
    #     self.unload_personalizations()
    
    def refresh_settings(self, target_ctx_path: str, new_value: Any) -> None:
        # print(f'refresh_settings: {target_ctx_path=}, {new_value=}')
        if target_ctx_path == self.enable_setting.path:
            if new_value:
                self.load_personalizations()
            else:
                # instead, we could just disable the tag here...
                self.unload_personalizations()

    def unload_personalizations(self, target_paths: List[str] = None) -> None:
        with self.personalization_mutex:
            if target_paths:
                for file_path in target_paths:
                    ctx_path = self.get_context_from_path(file_path)
                    if not ctx_path in self.personalizations:
                        raise Exception('unload_command_personalizations: no known context with path "{ctx_path}"')
                    
                    self.unwatch(file_path, self.update_personalizations)
                    self._purge_files(ctx_path)
            else:
                self.unwatch_all(self.unload_personalizations)
                self._purge_files()

    def unwatch_all(self, method_ref):
        watched_paths = self.get_watched_paths_for_method(method_ref)
        for p in watched_paths:
            print(f'unwatch_all: unwatching {path}')
            self.unwatch(p, method_ref)
            
    def _purge_files(self, path: str = None) -> None:
        with self.personalization_mutex:
            if path:
                sub_path = os.path.relpath(path, actions.path.talon_user())
                personal_path = self.personal_folder_path / sub_path

                os.remove(personal_path)
                
                ctx_path = self.get_context_from_path(path)
                del self.personalized_files[ctx_path]
            else:
                if os.path.exists(self.personal_folder_path):
                    rmtree(self.personal_folder_path)
                self.personalized_files = []

    def load_personalizations(self) -> None:
        with self.personalization_mutex:
            if self.enable_setting.get():
                self.ctx.tags = [self.personalization_tag_name_qualified]
                self.load_list_personalizations()
                self.load_command_personalizations()
                self.generate_files()
            else:
                self.ctx.tags = []
                self.unload_personalizations()
                return
   
    def load_one_list_context(self, caller_line_number, action, target_list, csv_file_path) -> Dict:
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
                deletions = self.load_count_items_per_row(1, csv_file_path)
            except ItemCountError:
                raise LoadError(f'{self.personal_list_control_file_name}, at line {caller_line_number} - files containing deletions must have just one value per line, skipping entire file: "{csv_file_path}"')
                
            except FileNotFoundError:
                raise LoadError(f'{self.personal_list_control_file_name}, at line {caller_line_number} - missing file for delete entry, skipping: "{csv_file_path}"')

            # print(f'personalize_file_name - {deletions=}')

            value = source.copy()
            value = { k:v for k,v in source.items() if k not in deletions }

        elif action.upper() == 'ADD' or action.upper() == 'REPLACE':
            additions = {}
            if csv_file_path:  # some REPLACE entries may not have filenames, and that's okay
                try:
                    for row in self.load_count_items_per_row(2, csv_file_path):
                        additions[ row[0] ] = row[1]
                except ItemCountError:
                    raise LoadError(f'{self.personal_list_control_file_name}, at line {caller_line_number} - files containing additions must have just two values per line, skipping entire file: "{csv_file_path}"')
                    
                except FileNotFoundError:
                    raise LoadError(f'{self.personal_list_control_file_name}, at line {caller_line_number} - missing file for add or replace entry, skipping: "{csv_file_path}"')
            
            if action.upper() == 'ADD':
                value = source.copy()
                
            # print(f'personalize_file_name - {additions=}')
            
            value.update(additions)
        else:
            raise LoadError(f'{self.personal_list_control_file_name}, at line {caller_line_number} - unknown action, skipping: "{action}"')

        return value
        
    def load_count_items_per_row(self, items_per_row: int, file_path: Path) -> List:
        items = []
        for row in self.get_lines_from_csv(file_path):
            if len(row) > items_per_row:
                # print(f'{self.personal_list_control_file_name}, at line {line_number} - files containing deletions must have just one value per line, skipping entire file: "{file_name}"')
                raise ItemCountError()
            items.append(row)

        return items

    def load_list_personalizations(self, target_contexts: List[str] = [], target_config_paths: List[str] = []) -> None:
        
        if target_contexts and target_config_paths:
            raise Exception('the skies will break for you')
            
        control_file = self.personal_csv_folder / self.personal_list_control_file_name
        
        print(f'load_list_personalizations: loading customizations from "{control_file}"...')
        
        if target_config_paths and control_file in target_config_paths:
            # if we're reloading the control file, then we're doing everything anyways
            target_config_paths = None

        # unwatch all config files until found again in the loop below
        watched_paths = self.get_watched_paths_for_method(self.update_csv)
        for path in watched_paths:
            if self.is_list_config_file(path):
                self.unwatch(path, self.update_csv)

        if os.path.exists(control_file):
            self.watch(control_file, self.update_csv)
        else:
            # nothing to do, apparently
            return
            
        try:
            line_number = 0
            for action, target_ctx_path, target_list, *remainder in self.get_lines_from_csv(control_file):
                line_number += 1

                csv_file_path = None
                if len(remainder):
                    csv_file_path = self.personal_csv_folder / self.personal_list_folder_name / remainder[0]
                    if os.path.exists(csv_file_path):
                        self.watch(csv_file_path, self.update_csv)
                    else:
                        print(f'load_list_personalizations: {control_file}, at line {line_number} - file not found for {action.upper()} entry, skipping: "{csv_file_path}"')
                        continue
                elif action.upper() != 'REPLACE':
                    print(f'load_list_personalizations: {control_file}, at line {line_number} - missing file name for {action.upper()} entry, skipping: "{target_list}"')
                    continue

                if target_contexts:
                    for ctx_path in target_contexts:
                        if target_ctx_path.startswith('user.' + ctx_path):
                            break
                    else:
                        print(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {target_ctx_path} not in {target_contexts}')
                        continue
                    
                if self.testing:
                    print(f'load_list_personalizations: {control_file}, at line {line_number} - {action, target_ctx_path, target_list, remainder}')

                if target_config_paths:
                    # note: this does the right thing even when csv_file_path is None
                    if str(csv_file_path) in target_config_paths:
                        print(f'load_list_personalizations: {control_file}, at line {line_number} - loading {csv_file_path}, because it is in "{target_config_paths}"')
                        target_config_paths.remove(str(csv_file_path))
                    else:
                        print(f'load_list_personalizations: {control_file}, at line {line_number} - SKIPPING {csv_file_path}, because it is NOT in "{target_config_paths}"')
                        continue

                if not target_ctx_path in registry.contexts:
                    print(f'load_list_personalizations: {control_file}, at line {line_number} - cannot redefine a context that does not exist, skipping: "{target_ctx_path}"')
                    continue
                
                if not target_list in registry.lists:
                    print(f'load_list_personalizations: {control_file}, at line {line_number} - cannot redefine a list that does not exist, skipping: "{target_list}"')
                    continue

                list_personalizations = self.get_list_personalizations(target_ctx_path)
                value = None
                try:
                    value = self.load_one_list_context(line_number, action, target_list, csv_file_path)
                except FilenameError as e:
                    print(str(e))
                    continue
                except LoadError as e:
                    print(str(e))
                    continue

                # print(f'load_list_personalizations: AFTER {action.upper()}, {value=}')

                list_personalizations.update({target_list: value})

                watch_path = self.get_fs_path_for_context(target_ctx_path)
                if not fs.tree.get(watch_path):                
                    self.watch(watch_path, self.update_personalizations)
        
        except FileNotFoundError as e:
            # below check is necessary because the inner try blocks above do not catch this error
            # completely...something's odd about the way talon is handling these exceptions.
            if os.path.basename(e.filename) == control_file:
                print(f'load_list_personalizations: Setting  "{self.setting_enable_personalization.path}" is enabled, but personalization control file does not exist: "{control_file}"')

    def get_fs_path_for_context(self, ctx_path):
        path_prefix, filename = self.split_context_to_user_path_and_file_name(ctx_path)
        path = os.path.join(actions.path.talon_user(), path_prefix, filename)
        
        if not ctx_path.endswith('.talon'):
            path = path + '.py'

        return path

    def watch(self, path, method_ref):
        # print(f'watch: {path=} {method_ref=}')
        short_path = Path(path).name
        print(f'watch: {short_path=}')

        fs.watch(path, method_ref)

    def unwatch(self, path, method_ref):
        # print(f'unwatch: {path=} {method_ref=}')
        short_path = Path(path).name
        print(f'unwatch: {short_path=}')

        fs.unwatch(path, method_ref)

    def load_one_command_context(self, caller_line_number, action, target_ctx_path, csv_file_name) -> Tuple[Dict, bool, str]:
        value = {}
        send_add_notification = False

        csv_file_path = os.path.join(self.personal_command_folder_name, csv_file_name)
        csv_file_path = self.personal_csv_folder / csv_file_name

        context = registry.contexts[target_ctx_path]

        commands = context.commands

        if action.upper() == 'DELETE':
            deletions = []
            try:
                deletions = self.load_count_items_per_row(1, csv_file_path)
            except ItemCountError:
                raise LoadError(f'load_command_personalizations: {self.personal_command_control_file_name}, at line {caller_line_number} - files containing deletions must have just one value per line, skipping entire file: "{csv_file_path}"')
            except FileNotFoundError:
                raise LoadError(f'load_command_personalizations: {self.personal_command_control_file_name}, at line {caller_line_number} - missing file for delete entry, skipping: "{csv_file_path}"')

            # print(f'personalize_file_name - {deletions=}')
            value = { k: 'skip()' for k in commands.keys() if k in deletions }
            
        elif action.upper() == 'REPLACE':
            additions = {}
            try:
                for row in self.load_count_items_per_row(2, csv_file_path):
                    target_command = row[0]
                    replacement_command = row[1]

                    try:
                        impl = commands[f'{target_command}'].target.code
                    except KeyError as e:
                        raise LoadError(f'load_command_personalizations: {self.personal_command_control_file_name}, at line {caller_line_number} - cannot replace a command that does not exist, skipping: "{target_command}"')
                    
                    additions[ target_command ] = 'skip()'
                    additions[ replacement_command ] = impl
            except ItemCountError:
                raise LoadError(f'{self.personal_list_control_file_name}, at line {caller_line_number} - files containing additions must have just two values per line, skipping entire file: "{csv_file_name}"')
            except FileNotFoundError:
                raise LoadError(f'load_command_personalizations: {self.personal_command_control_file_name}, at line {caller_line_number} - missing file for add or replace entry, skipping: "{csv_file_path}"')
            
            value.update(additions)
        else:
            if action.upper() == 'ADD':
                send_add_notification = True
                
            raise LoadError(f'load_command_personalizations: {self.personal_command_control_file_name}, at line {caller_line_number} - unknown action, skipping: "{action}"')

        # print(f'load_command_personalizations: AFTER {action.upper()}, {value=}')
        
        return value, send_add_notification, csv_file_path

    def load_command_personalizations(self, target_contexts: List[str] = [], target_config_paths: List[str] = []) -> None:
        
        if target_contexts and target_config_paths:
            raise Exception('the skies will break for you too')

        send_add_notification = False
        
        control_file = self.personal_csv_folder / self.personal_command_control_file_name

        print(f'load_command_personalizations: loading customizations from "{control_file}"...')
        
        if target_config_paths and control_file in target_config_paths:
            # if we're reloading the control file, then we're doing everything anyways
            target_config_paths = None
            
        # unwatch all config files until found again in the loop below
        watched_paths = self.get_watched_paths_for_method(self.update_csv)
        for path in watched_paths:
            if self.is_command_config_file(path):
                self.unwatch(path, self.update_csv)

        if os.path.exists(control_file):
            self.watch(control_file, self.update_csv)
        else:
            # nothing to do, apparently
            return
            
        try:
            line_number = 0
            for action, target_ctx_path, csv_file_name in self.get_lines_from_csv(control_file):
                line_number += 1

                csv_file_path = self.personal_csv_folder / self.personal_command_folder_name / csv_file_name
                if os.path.exists(csv_file_path):
                    self.watch(csv_file_path, self.update_csv)
                else:
                    print(f'load_command_personalizations: {control_file}, at line {line_number} - file not found for {action.upper()} entry, skipping: "{csv_file_path}"')
                    continue
                
                if self.testing:
                    # print(f'{control_file}, at line {line_number} - {target, action, remainder}')
                    print(f'load_command_personalizations: {control_file}, at line {line_number} - {target_ctx_path, action, csv_file_name}')

                if not target_ctx_path in registry.contexts:
                    print(f'load_command_personalizations: {control_file}, at line {line_number} - cannot personalize commands in a context that does not exist, skipping: "{target_ctx_path}"')
                    continue

                if target_contexts and not target_ctx_path in target_contexts:
                    continue

                if target_config_paths:
                    if csv_file_path in target_config_paths:
                        target_config_paths.remove(csv_file_path)
                    else:
                        continue

                command_personalizations = self.get_command_personalizations(target_ctx_path)

                value = None
                try:
                    value, send_add_notification, file_path = self.load_one_command_context(line_number, action, target_ctx_path, csv_file_path)
                except LoadError as e:
                    print(str(e))
                    continue

                command_personalizations.update(value)

                watch_path = self.get_fs_path_for_context(target_ctx_path)
                self.watch(watch_path, self.update_personalizations)

        except FilenameError as e:
            print(str(e))
        except FileNotFoundError as e:
            # below check is necessary because the inner try blocks above do not catch this
            # error completely...something's odd about the way talon is handling these exceptions.
            print(f'personalize_file_name - {e.filename}')
            if os.path.basename(e.filename) == control_file:
                print(f'Setting  "{self.setting_enable_personalization.path}" is enabled, but personalization control file does not exist: "{control_file}"')

        if target_config_paths:
            # WIP - need to check the case where a config path has been deleted
            print(f'load_command_personalizations: failed to process some targeted config paths: "{target_config_paths}"')

        # WIP - review this, repeated notifications will be annoying if there are many file updates
        if send_add_notification:
            app.notify(
                title=self.command_add_disallowed_title,
                body=self.command_add_disallowed_notice
            )

    def add_tag_to_match_string(self, context_path: str, old_match_string: str, tag: str = None) -> str:
        if tag is None:
            tag = self.tag_expression

        new_match_string: str = old_match_string + tag

        # print(f'{old_match_string=}, {new_match_string=}')
        return new_match_string

    def split_context_to_user_path_and_file_name(self, context_path: str) -> Path:

        # figure out separation point between the filename and it's parent path
        filename_idx = -1
        if context_path.endswith('.talon'):
            filename_idx = -2

        # split context path to separate filename and parent path
        user_path = context_path.split('.')

        # extract the filename component
        filename = '.'.join(user_path[filename_idx:])
            
        # extract the parent path
        start_idx = 0
        if user_path[0] == 'user':
            # skip the leading 'user' bit
            start_idx = 1
        else:
            raise Exception('cannot override non-user paths at this time')
        user_path = f'{os.path.sep}'.join(user_path[start_idx:filename_idx])
        
        # print(f'get_fs_path_prefix: got {context_path}, returning {wip, filename}')

        return user_path, filename

    def write_py_header(self, f, context_path: str) -> None:
        header = self.py_header.format(context_path, self.personal_folder_name)
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
        print(f'generate_files: writing customizations to "{self.personal_folder_path}"...')
        
        self._purge_files()

        # print(f'generate_files: HERE "{self.personalizations}"')
            
        for ctx_path in self.personalizations:
            # print(f'generate_files: {ctx_path=}')

            filepath_prefix = self.get_personal_filepath_prefix(ctx_path)
            # print(f'generate_files: {filepath_prefix=}')
            
            source_match_string = self.get_source_match_string(ctx_path)
            # print(f'generate_files: {source_match_string=}')
            
            self.update_one_file(ctx_path, filepath_prefix, source_match_string)

    def update_one_file(self, ctx_path, filepath_prefix, source_match_string):
        new_match_string = self.add_tag_to_match_string(ctx_path, source_match_string)

        # WIP - verify if this check is really necessary
        if filepath_prefix in self.personalized_files:
            # append to existing
            print(f'update_one_file: APPEND TO EXISTING - {ctx_path=}, {filepath_prefix=}')
            open_mode = 'a'
        else:
            # truncate on open, if the file actually exists
            open_mode = 'w'
            self.personalized_files.append(filepath_prefix)

        # print(f'update_one_file: {ctx_path=}, {new_match_string=}')

        if ctx_path.endswith('.talon'):
            command_personalizations = self.get_command_personalizations(ctx_path)
            filepath = str(filepath_prefix)
            print(f'update_one_file: writing command customizations to "{filepath}"...')
            with open(filepath, open_mode) as f:
                self.write_talon_header(f, ctx_path)
                    
                self.write_talon_context(f, new_match_string)
                    
                self.write_talon_tag_calls(f, ctx_path)
                    
                # print(f'update_one_file: {command_personalizations=}')
                for personal_command, personal_impl in command_personalizations.items():
                    print(f'{personal_command}:', file=f)
                    for line in personal_impl.split('\n'):
                        print(f'\t{line}', file=f)

        else:
            list_personalizations = self.get_list_personalizations(ctx_path)
            filepath = str(filepath_prefix) + '.py'
            print(f'update_one_file: writing list customizations to "{filepath}"...')
            with open(filepath, open_mode) as f:
                self.write_py_header(f, ctx_path)
                self.write_py_context(f, new_match_string)
                pp = pprint.PrettyPrinter(indent=4)
                for list_name, list_value in list_personalizations.items():
                    print(f'ctx.lists["{list_name}"] = {pp.pformat(list_value)}\n', file=f)

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
        path_prefix, filename = self.split_context_to_user_path_and_file_name(context_path)
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
        path_prefix, filename = self.split_context_to_user_path_and_file_name(context_path)
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

    def get_lines_from_csv(self, path_string: str, escapechar: str ='\\') -> List[str]:
        """Retrieves contents of CSV file in settings dir, without tracking"""
        
        path = Path(path_string)
        
        if not self.personal_csv_folder in path.parents:
            raise Exception(f'get_lines_from_csv: file must be in the config folder, "self.personal_csv_folder", skipping: {path}')

        if not path.suffix == ".csv":
            raise FilenameError(f'get_lines_from_csv: file name must end in ".csv", skipping: {path}')

        rows = []
        with open(str(path), "r") as f:
            rows = list(csv.reader(f, escapechar=escapechar))

        # print(f'get_lines_from_csv: returning {rows}')
        return rows

    def get_context_from_path(self, path):
        temp = os.path.relpath(path, actions.path.talon_user())
        if not path.endswith('.talon'):
            # remove the the file extension
            temp, _ = os.path.splitext(temp)
        ctx_path = temp.replace(os.path.sep, '.')
        return ctx_path

    def is_list_config_file(self, path):
        return Path.is_file(Path(path)) and self.personal_list_folder_name == self.get_config_category(path)
    
    def is_command_config_file(self, path):
        return Path.is_file(Path(path)) and self.personal_command_folder_name == self.get_config_category(path)
    
    def get_config_category(self, path):
        temp = os.path.relpath(path, self.personal_csv_folder)
        temp = temp.split(os.path.sep)

        category = None
        if temp[0] == self.personal_list_folder_name or temp[0] == self.personal_command_folder_name:
            # raise Exception(f'get_config_category: not a personalization config file: {path}')
            category = temp[0]
            
        # print(f'get_config_category: returning {category}')
        return category

    def update_personalizations(self, path: str, flags: Any) -> None:
        print(f'update_personalizations: starting - {path, flags}')
        reload = flags.exists
        if reload:
            ctx_path = self.get_context_from_path(path)
            print(f'update_personalizations: {ctx_path=}')
            if ctx_path.endswith('.talon'):
                self.load_command_personalizations(target_contexts = [ctx_path])
            else:
                self.load_list_personalizations(target_contexts = [ctx_path])
        else:
            self.unload_personalizations(target_paths = [path])
            
    def update_csv(self, path: str, flags: Any) -> None:
        if testing:
            print(f'update_csv: starting - {path, flags}')
            watched_paths = self.get_watched_paths_for_method(self.update_csv)
            matching_paths = [p for p in watched_paths if p == path]
            print(f'update_csv: TESTING: {len(watched_paths), len(matching_paths)}')

        reload = flags.exists
        if reload:
            if self.is_list_config_file(path):
                self.load_list_personalizations(target_config_paths = [path])
            elif self.is_command_config_file(path):
                self.load_command_personalizations(target_config_paths = [path])
            else:
                raise Exception(f'update_personalizations: unrecognized file: {path}')
        else:
            self.unload_personalizations(target_paths = [path])

    def get_watched_paths_for_method(self, method: Callable):
        path_to_callback_map = dict({k: v[0][0] for k,v in fs.tree.walk()})
        paths = [k for k,v in path_to_callback_map.items() if v == method]
        return paths

def on_ready() -> None:
    print('ON READY')
    personalizer.load_personalizations()

    # catch updates
    settings.register("", personalizer.refresh_settings)
        
personalizer = Personalizer()

app.register("ready", on_ready)
