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
import logging

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

        # the tag used to enable/disable personalized contexts
        self.personalization_tag_name = 'personalization'
        self.personalization_tag_name_qualified = 'user.' + self.personalization_tag_name
        self.personalization_tag = self.mod.tag(self.personalization_tag_name, desc='enable personalizations')

        self.ctx = Context()
        self.ctx.matches = f'tag: {self.personalization_tag_name_qualified}'
        
        # data structure used to store metadata for all personalized contexts
        self.personalizations = {}

        self.control_file_name = 'control.csv'

        # folder where personalized contexts are kept
        self.personal_folder_name = '_personalizations'
        self.personal_folder_path = Path(__file__).parents[1] / self.personal_folder_name
        
        # where config files are stored
        self.personal_config_folder_name = 'csv'
        self.personal_config_folder = Path(__file__).parents[1] / self.personal_config_folder_name

        # config sub folder for list personalizations
        self.personal_list_folder_name = 'list_personalization'
        self.personal_list_control_file_name = os.path.join(self.personal_list_folder_name, self.control_file_name)

        # config sub folder for command personalizations
        self.personal_command_folder_name = 'command_personalization'
        self.personal_command_control_file_name = os.path.join(self.personal_command_folder_name, self.control_file_name)
        
        # text for notifying user of a configuration error
        self.command_add_disallowed_title = "Talon - ADD not allowed for commands"
        self.command_add_disallowed_notice = 'Command personalization: to add new commands, use a .talon file.'
        
        # self.deleted_context_title = "Talon - personalization source file disappeared"
        # self.deleted_context_notice = 'Personalization: personalizations have been invalidated because the source file has disappeared.'

        self.testing = True
  
        # header written to personalized context files
        self.personalized_header = r"""
# DO NOT MODIFY THIS FILE - it has been dynamically generated in order to override some of
# the definitions from context '{}'.
#
# To customize this file, copy it to a different location outside the '{}'
# folder. Be sure you understand how Talon context matching works, so you can avoid conflicts
# with this file. If you do that, you may also want to remove the control file line that
# creates this file.
#"""

        # tag for personalized context matches
        self.tag_expression = f'tag: {self.personalization_tag_name_qualified}'

    # def __del__(self) -> None:
    #     print(f'__del__: UNLOADING PERSONALIZATIONS ON OBJECT DESTRUCTION')
    #     self.unload_personalizations()
    
    def refresh_settings(self, target_ctx_path: str, new_value: Any) -> None:
        """Callback for handling Talon settings changes"""
        # print(f'refresh_settings: {target_ctx_path=}, {new_value=}')
        if target_ctx_path == self.enable_setting.path:
            if new_value:
                # personalizations have been enabled, load them in
                self.load_personalizations()
            else:
                # personalizations have been disabled, unload them
                # instead, we could just disable the tag here...
                self.unload_personalizations()

    def unload_personalizations(self, target_paths: List[str] = None) -> None:
        """Unload some (or all) personalized contexts."""
        with self.personalization_mutex:
            if target_paths:
                for file_path in target_paths:
                    ctx_path = self.get_context_from_path(file_path)
                    if not ctx_path in self.personalizations:
                        raise Exception('unload_command_personalizations: no known context with path "{ctx_path}"')
                    
                    self._unwatch(file_path, self.update_personalizations)
                    self._purge_files(ctx_path)
            else:
                self._unwatch_all(self.unload_personalizations)
                self._purge_files()

    def _unwatch_all(self, method_ref):
        """Internal method to stop watching all watched files associated with given method reference."""
        watched_paths = self._get_watched_paths_for_method(method_ref)
        for p in watched_paths:
            if self.testing:
                print(f'unwatch_all: unwatching {path}')
            self._unwatch(p, method_ref)
            
    def _purge_files(self, path: str = None) -> None:
        """Internal method to remove all files storing personalized contexts."""
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
        """Load/unload defined personalizations, based on whether the feature is enabled or not."""
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
   
    def load_one_list_context(self, action, target_list, config_file_path) -> Dict:
        """Load a single list context."""
        
        try:
            # WIP - need to review this, is it correct?
            if target_list in self.ctx.lists.keys():
                # print(f'WE DO ACTUALLY GET HERE SOMETIMES')
                # source = self.ctx.lists[target_list]
                raise Exception(f'load_one_list_context: not overwriting in-memory list')
            else:
                source = registry.lists[target_list][0]
        except KeyError as e:
            raise LoadError(f'cannot redefine a list that does not exist, skipping: "{target_list}"')

        value = {}
        if action.upper() == 'DELETE':
            deletions = []
            try:
                # load items from config file
                deletions = self._load_count_items_per_row(1, config_file_path)
            except ItemCountError:
                raise LoadError(f'files containing deletions must have just one value per line, skipping entire file: "{config_file_path}"')
                
            except FileNotFoundError:
                raise LoadError(f'missing file for delete entry, skipping: "{config_file_path}"')

            # print(f'personalize_file_name - {deletions=}')

            value = source.copy()
            value = { k:v for k,v in source.items() if k not in deletions }

        elif action.upper() == 'ADD' or action.upper() == 'REPLACE':
            additions = {}
            if config_file_path:  # some REPLACE entries may not have filenames, and that's okay
                try:
                    for row in self._load_count_items_per_row(2, config_file_path):
                        additions[ row[0] ] = row[1]
                except ItemCountError:
                    raise LoadError(f'files containing additions must have just two values per line, skipping entire file: "{config_file_path}"')
                    
                except FileNotFoundError:
                    raise LoadError(f'missing file for add or replace entry, skipping: "{config_file_path}"')
            
            if action.upper() == 'ADD':
                value = source.copy()
                
            # print(f'personalize_file_name - {additions=}')
            
            value.update(additions)
        else:
            raise LoadError(f'unknown action, skipping: "{action}"')

        return value
        
    def _load_count_items_per_row(self, items_per_row: int, file_path: Path) -> List:
        """Internal method to read a CSV file expected to have a fixed number of items per row."""
        items = []
        for row in self.get_lines_from_csv(file_path):
            if len(row) > items_per_row:
                raise ItemCountError()
            items.append(row)

        return items

    def load_list_personalizations(self, target_contexts: List[str] = [], target_config_paths: List[str] = []) -> None:
        """Load some (or all) defined list personalizations."""
        
        if target_contexts and target_config_paths:
            raise ValueError('load_list_personalizations: bad arguments - cannot accept both "target_contexts" and "target_config_paths" at the same time.')
            
        control_file = self.personal_config_folder / self.personal_list_control_file_name
        
        if self.testing:
            print(f'load_list_personalizations: loading customizations from "{control_file}"...')
        
        if target_config_paths and control_file in target_config_paths:
            # if we're reloading the control file, then we're doing everything anyways
            target_config_paths = None

        # unwatch all config files until found again in the loop below
        watched_paths = self._get_watched_paths_for_method(self.reload_config)
        for path in watched_paths:
            if self.is_list_config_file(path):
                self._unwatch(path, self.reload_config)

        if os.path.exists(control_file):
            self._watch(control_file, self.reload_config)
        else:
            # nothing to do, apparently
            return
            
        try:
            # loop through the control file and do the needful
            line_number = 0
            for action, target_ctx_path, target_list, *remainder in self.get_lines_from_csv(control_file):
                line_number += 1

                # determine the CSV file path, check error cases and establish config file watches
                config_file_path = None
                if len(remainder):
                    config_file_path = self.personal_config_folder / self.personal_list_folder_name / remainder[0]
                    if os.path.exists(config_file_path):
                        self._watch(config_file_path, self.reload_config)
                    else:
                        logging.error(f'load_list_personalizations: file not found for {action.upper()} entry, skipping: "{config_file_path}"')
                        continue
                elif action.upper() != 'REPLACE':
                    logging.error(f'load_list_personalizations: missing file name for {action.upper()} entry, skipping: "{target_list}"')
                    continue

                if target_contexts:
                    # we are loading some, not all, contexts. see if the current target matches given list.
                    for ctx_path in target_contexts:
                        # this will need to change if we ever want to override any context other than 'user'.
                        if target_ctx_path.startswith('user.' + ctx_path):
                            break
                    else:
                        # current target is not in the list of targets, skip
                        if self.testing:
                            print(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {target_ctx_path} not in given list of target contexts')
                        continue
                    
                if self.testing:
                    print(f'{action, target_ctx_path, target_list, remainder}')

                if target_config_paths:
                    # we are loading some, not all, paths. see if the current path matches our list.
                    # note: this does the right thing even when config_file_path is None, which is sometimes the case.
                    if str(config_file_path) in target_config_paths:
                        # print(f'loading {config_file_path}, because it is in "{target_config_paths}"')
                        
                        # consume the list as we go so at the end we know if we missed any paths
                        target_config_paths.remove(str(config_file_path))
                    else:
                        if self.testing:
                            print(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {config_file_path} is NOT in given list of target config paths')
                        continue

                if not target_ctx_path in registry.contexts:
                    logging.error(f'load_list_personalizations: cannot redefine a context that does not exist, skipping: "{target_ctx_path}"')
                    continue
                
                # load the target context
                list_personalizations = self.get_list_personalizations(target_ctx_path)
                value = None
                try:
                    value = self.load_one_list_context(action, target_list, config_file_path)
                except FilenameError as e:
                    logging.error(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {str(e)}')
                    continue
                except LoadError as e:
                    logging.error(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {str(e)}')
                    continue

                # print(f'load_list_personalizations: AFTER {action.upper()}, {value=}')

                # add the new data
                list_personalizations.update({target_list: value})

                # make sure we are monitoring the source file for changes
                self._watch_source_file_for_context(target_ctx_path, self.update_personalizations)
        
        except FileNotFoundError as e:
            # below check is necessary because the inner try blocks above do not catch this error
            # completely...something's odd about the way talon is handling these exceptions.
            logging.warning(f'load_list_personalizations: setting "{self.setting_enable_personalization.path}" is enabled, but personalization config file does not exist: "{e.filename}"')

    def _watch_source_file_for_context(self, ctx_path, method_ref):
        """Internal method to watch the file associated with a given context."""
        watch_path = self.get_fs_path_for_context(ctx_path)
        if not fs.tree.get(watch_path):                
            self._watch(watch_path, method_ref)

    def get_fs_path_for_context(self, ctx_path):
        """Convert given Talon context path into the equivalent filesystem path."""
        path_prefix, filename = self._split_context_to_user_path_and_file_name(ctx_path)
        path = os.path.join(actions.path.talon_user(), path_prefix, filename)
        
        if not ctx_path.endswith('.talon'):
            path = path + '.py'

        return path

    def _watch(self, path, method_ref):
        """Internal wrapper method to set a file watch."""

        # if self.testing:
        #     # print(f'watch: {path=} {method_ref=}')
        #     short_path = Path(path).name
        #     print(f'watch: {short_path=}')

        fs.watch(path, method_ref)

    def _unwatch(self, path, method_ref):
        """Internal wrapper method to clear (unset) a file watch."""
        
        # if self.testing:
        #     # print(f'unwatch: {path=} {method_ref=}')
        #     short_path = Path(path).name
        #     print(f'unwatch: {short_path=}')

        fs.unwatch(path, method_ref)

    def load_one_command_context(self, action, target_ctx_path, config_file_name) -> Tuple[Dict, bool, str]:
        """Load a single command context."""
        value = {}
        send_add_notification = False

        config_file_path = os.path.join(self.personal_command_folder_name, config_file_name)
        config_file_path = self.personal_config_folder / config_file_name

        context = registry.contexts[target_ctx_path]

        commands = context.commands

        if action.upper() == 'DELETE':
            deletions = []
            try:
                # load items from source file
                deletions = self._load_count_items_per_row(1, config_file_path)
            except ItemCountError:
                raise LoadError(f'files containing deletions must have just one value per line, skipping entire file: "{config_file_path}"')
            except FileNotFoundError:
                raise LoadError(f'missing file for delete entry, skipping: "{config_file_path}"')

            # print(f'personalize_file_name - {deletions=}')
            value = { k: 'skip()' for k in commands.keys() if k in deletions }
            
        elif action.upper() == 'REPLACE':
            additions = {}
            try:
                # load items from source file
                for row in self._load_count_items_per_row(2, config_file_path):
                    target_command = row[0]
                    replacement_command = row[1]

                    try:
                        # fetch the command implementation from Talon
                        impl = commands[f'{target_command}'].target.code
                    except KeyError as e:
                        raise LoadError(f'cannot replace a command that does not exist, skipping: "{target_command}"')
                    
                    # accumulate values
                    additions[ target_command ] = 'skip()'
                    additions[ replacement_command ] = impl
            except ItemCountError:
                raise LoadError(f'files containing additions must have just two values per line, skipping entire file: "{config_file_name}"')
            except FileNotFoundError:
                raise LoadError(f'missing file for add or replace entry, skipping: "{config_file_path}"')
            
            # capture the additions
            value.update(additions)
        else:
            if action.upper() == 'ADD':
                # to add new commands, the user should use a .talon file
                send_add_notification = True
                
            raise LoadError(f'unknown action, skipping: "{action}"')

        # print(f'load_command_personalizations: AFTER {action.upper()}, {value=}')
        
        return value, send_add_notification

    def load_command_personalizations(self, target_contexts: List[str] = [], target_config_paths: List[str] = []) -> None:
        """Load some (or all) defined command personalizations."""

        if target_contexts and target_config_paths:
            raise ValueError('load_command_personalizations: bad arguments - cannot accept both "target_contexts" and "target_config_paths" at the same time.')

        # decide whether or not to send the user a notification before returning
        send_add_notification = False
        
        control_file = self.personal_config_folder / self.personal_command_control_file_name

        if self.testing:
            print(f'load_command_personalizations: loading customizations from "{control_file}"...')
        
        if target_config_paths and control_file in target_config_paths:
            # if we're reloading the control file, then we're doing everything anyways
            target_config_paths = None
            
        # unwatch all config files until found again in the loop below
        watched_paths = self._get_watched_paths_for_method(self.reload_config)
        for path in watched_paths:
            if self.is_command_config_file(path):
                self._unwatch(path, self.reload_config)

        if os.path.exists(control_file):
            self._watch(control_file, self.reload_config)
        else:
            # nothing to do, apparently
            return
            
        try:
            # loop through the control file and do the needful
            line_number = 0
            for action, target_ctx_path, config_file_name in self.get_lines_from_csv(control_file):
                line_number += 1

                # determine the CSV file path, check error cases and establish config file watches
                config_file_path = self.personal_config_folder / self.personal_command_folder_name / config_file_name
                if os.path.exists(config_file_path):
                    self._watch(config_file_path, self.reload_config)
                else:
                    logging.error(f'load_command_personalizations: {control_file}, at line {line_number} - file not found for {action.upper()} entry, skipping: "{config_file_path}"')
                    continue
                
                if self.testing:
                    # print(f'{control_file}, at line {line_number} - {target, action, remainder}')
                    print(f'load_command_personalizations: {control_file}, at line {line_number} - {target_ctx_path, action, config_file_name}')

                if target_contexts and not target_ctx_path in target_contexts:
                    # current target is not in the list of targets, skip
                    if self.testing:
                        print(f'load_command_personalizations: {control_file}, SKIPPING at line {line_number} - {target_ctx_path} not in list of target contexts')
                    continue

                if target_config_paths:
                    if config_file_path in target_config_paths:
                        # consume the list as we go so at the end we know if we missed any paths
                        target_config_paths.remove(config_file_path)
                    else:
                        if self.testing:
                            print(f'load_command_personalizations: {control_file}, SKIPPING at line {line_number} - {config_file_path} is NOT in given list of target config paths')
                        continue

                if not target_ctx_path in registry.contexts:
                    logging.error(f'load_command_personalizations: {control_file}, at line {line_number} - cannot personalize commands for a context that does not exist, skipping: "{target_ctx_path}"')
                    continue

                command_personalizations = self.get_command_personalizations(target_ctx_path)

                value = None
                try:
                    value, send_add_notification = self.load_one_command_context(action, target_ctx_path, config_file_path)
                except LoadError as e:
                    logging.error(f'load_command_personalizations: {control_file}, at line {line_number} - {str(e)}')
                    continue

                command_personalizations.update(value)

                self._watch_source_file_for_context(target_ctx_path, self.update_personalizations)

        except FilenameError as e:
            logging.error(f'load_command_personalizations: {control_file}, at line {line_number} - {str(e)}')
        except FileNotFoundError as e:
            # this block is necessary because the inner try blocks above do not catch this error
            # completely ...something's odd about the way talon is handling these exceptions.
            logging.warning(f'load_command_personalizations: setting "{self.setting_enable_personalization.path}" is enabled, but personalization config file does not exist: "{e.filename}"')

        if target_config_paths:
            logging.error(f'load_command_personalizations: failed to process some targeted config paths: "{target_config_paths}"')

        # repeated notifications are annoying, the user can just fix their config file to make them stop.
        if send_add_notification:
            app.notify(
                title=self.command_add_disallowed_title,
                body=self.command_add_disallowed_notice
            )

    def _add_tag_to_match_string(self, context_path: str, old_match_string: str, tag: str = None) -> str:
        """Internal function to add personalization tag to given match string."""
        if tag is None:
            tag = self.tag_expression

        new_match_string: str = old_match_string + tag

        # print(f'{old_match_string=}, {new_match_string=}')
        return new_match_string

    def _split_context_to_user_path_and_file_name(self, context_path: str) -> Path:
        """Internal function for extracting filesystem path information from Talon context path."""
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

    def _write_py_header(self, f, context_path: str) -> None:
        """Internal method for writing header to Talon python file."""
        header = self.personalized_header.format(context_path, self.personal_folder_name)
        print(header, file=f)

    def _write_py_context(self, f, match_string: str) -> None:
        """Internal method for writing context definition to Talon python file."""
        print('from talon import Context', file=f)
        print('ctx = Context()', file=f)
        print(f'ctx.matches = """{match_string}"""\n', file=f)

    def _write_talon_header(self, f, context_path: str) -> None:
        """Internal method for writing header to .talon file."""
        header = self.personalized_header.format(context_path, self.personal_folder_name)
        print(header, file=f)

    def _write_talon_context(self, f, match_string: str) -> None:
        """Internal method for writing context definition to .talon file."""
        print(f'{match_string}\n-', file=f)
        
    def _write_talon_tag_calls(self, f, context_path: str) -> None:
        """Internal method for writing tag calls to .talon file."""
        for line in self.get_tag_calls(context_path):
            print(line, file=f, end='')
        print(file=f)

    def generate_files(self) -> None:
        """Generate personalization files from current metadata."""
        if self.testing:
            print(f'generate_files: writing customizations to "{self.personal_folder_path}"...')
        
        self._purge_files()

        # print(f'generate_files: HERE "{self.personalizations}"')
            
        for ctx_path in self.personalizations:
            # print(f'generate_files: {ctx_path=}')

            filepath_prefix = self.get_personal_filepath_prefix(ctx_path)
            # print(f'generate_files: {filepath_prefix=}')
            
            source_match_string = self.get_source_match_string(ctx_path)
            # print(f'generate_files: {source_match_string=}')
            
            self.write_one_file(ctx_path, filepath_prefix, source_match_string)

    def write_one_file(self, ctx_path, file_path, source_match_string):
        """Generate one personalized file"""
        new_match_string = self._add_tag_to_match_string(ctx_path, source_match_string)

        # WIP - verify if this check is really necessary
        if file_path in self.personalized_files:
            # # append to existing
            # print(f'update_one_file: APPEND TO EXISTING - {ctx_path=}, {file_path=}')
            # open_mode = 'a'
            raise Exception(f'write_one_file: not overwriting existing file: {file_path}')
        else:
            # truncate on open, if the file actually exists
            open_mode = 'w'
            self.personalized_files.append(file_path)

        # print(f'update_one_file: {ctx_path=}, {new_match_string=}')

        if ctx_path.endswith('.talon'):
            command_personalizations = self.get_command_personalizations(ctx_path)
            file_path = str(file_path)

            if self.testing:
                print(f'update_one_file: writing command customizations to "{file_path}"...')
                
            with open(file_path, open_mode) as f:
                self._write_talon_header(f, ctx_path)
                    
                self._write_talon_context(f, new_match_string)
                    
                self._write_talon_tag_calls(f, ctx_path)
                    
                # print(f'update_one_file: {command_personalizations=}')
                for personal_command, personal_impl in command_personalizations.items():
                    print(f'{personal_command}:', file=f)
                    for line in personal_impl.split('\n'):
                        print(f'\t{line}', file=f)

        else:
            list_personalizations = self.get_list_personalizations(ctx_path)
            file_path = str(file_path) + '.py'

            if self.testing:
                print(f'update_one_file: writing list customizations to "{file_path}"...')
                
            with open(file_path, open_mode) as f:
                self._write_py_header(f, ctx_path)
                self._write_py_context(f, new_match_string)
                pp = pprint.PrettyPrinter(indent=4)
                for list_name, list_value in list_personalizations.items():
                    print(f'ctx.lists["{list_name}"] = {pp.pformat(list_value)}\n', file=f)

    def get_source_match_string(self, context_path: str) -> str:
        """Return context match string for given context."""
        source_match_string = None

        context_personalizations = self.get_personalizations(context_path)
        if 'source_context_match_string' in context_personalizations:
            source_match_string = context_personalizations['source_context_match_string']
        else:
            source_match_string, _ = self._load_matches_and_tags(context_path)
            
        return source_match_string
    
    def get_tag_calls(self, context_path: str) -> List[str]:
        """Return tag calls for given context."""
        tag_calls = None
        context_personalizations = self.get_personalizations(context_path)
        if 'tag_calls' in context_personalizations:
            tag_calls = context_personalizations['tag_calls']
        else:
            _, tag_calls = self._load_matches_and_tags(context_path)
            
        return tag_calls

    def _load_matches_and_tags(self, context_path: str) -> Union[str, List[str]]:
        """Internal method to return match string and tags for given context."""
        source_match_string, tag_calls = None, None
        if context_path.endswith('.talon'):
            # need to grab match string from the file
            source_match_string, tag_calls = self._parse_talon_file(context_path)
        else:
            context = self.get_source_context(context_path)
            source_match_string = context.matches

        context_personalizations = self.get_personalizations(context_path)
        context_personalizations['source_context_match_string'] = source_match_string
        context_personalizations['tag_calls'] = tag_calls
        
        return source_match_string, tag_calls

    def _parse_talon_file(self, context_path: str) -> Union[str, List[str]]:
        """Internal method to extract match string and tags from the source file for a given context."""
        path_prefix, filename = self._split_context_to_user_path_and_file_name(context_path)
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
        """Return the personalized file path for the given context"""
        path_prefix, filename = self._split_context_to_user_path_and_file_name(context_path)
        path = self.personal_folder_path / path_prefix
        if not os.path.exists(path):
            os.makedirs(path, mode=550, exist_ok=True)
            
        filepath_prefix = path / filename
        return filepath_prefix

    def get_personalizations(self, context_path: str) -> Dict:
        """Return personalizations for given context path"""
        if not context_path in self.personalizations:
            self.personalizations[context_path] = {}

        return self.personalizations[context_path]

    def get_source_context(self, context_path: str) -> Dict:
        """Return Talon context reference for given context path."""
        context_personalizations = self.get_personalizations(context_path)

        if not 'source_context' in context_personalizations:
            context_personalizations['source_context'] = registry.contexts[context_path]

        return context_personalizations['source_context']
        
    def get_list_personalizations(self, context_path: str) -> Dict:
        """Return list personalizations for given context path"""
        context_personalizations = self.get_personalizations(context_path)

        if not 'lists' in context_personalizations:
            context_personalizations['lists'] = {}
            
        return context_personalizations['lists']

    def get_command_personalizations(self, context_path: str) -> Dict:
        """Returned command personalizations for given context path"""
        context_personalizations = self.get_personalizations(context_path)

        if not 'commands' in context_personalizations:
            context_personalizations['commands'] = {}
            
        return context_personalizations['commands']

    def get_lines_from_csv(self, path_string: str, escapechar: str ='\\') -> List[str]:
        """Retrieves contents of CSV file in personalization config folder."""
        
        path = Path(path_string)
        
        if not self.personal_config_folder in path.parents:
            raise Exception(f'get_lines_from_csv: file must be in the config folder, "self.personal_csv_folder", skipping: {path}')

        if not path.suffix == ".csv":
            raise FilenameError(f'get_lines_from_csv: file name must end in ".csv", skipping: {path}')

        rows = []
        with open(str(path), "r") as f:
            rows = list(csv.reader(f, escapechar=escapechar))

        # print(f'get_lines_from_csv: returning {rows}')
        return rows

    def get_context_from_path(self, path):
        """Returns Talon context path corresponding to given filesystem path."""
        temp = os.path.relpath(path, actions.path.talon_user())
        if not path.endswith('.talon'):
            # remove the the file extension
            temp, _ = os.path.splitext(temp)
        ctx_path = temp.replace(os.path.sep, '.')
        return ctx_path

    def is_list_config_file(self, path):
        """Checks whether given path is under the list personalization config folder."""
        return Path.is_file(Path(path)) and self.personal_list_folder_name == self.get_config_category(path)
    
    def is_command_config_file(self, path):
        """Checks whether given path is under the command personalization config folder."""
        return Path.is_file(Path(path)) and self.personal_command_folder_name == self.get_config_category(path)
    
    def get_config_category(self, path):
        """Return parent directory name of given path relative to the personalization configuration folder, e.g. list_personalization"""
        temp = os.path.relpath(path, self.personal_config_folder)
        temp = temp.split(os.path.sep)

        category = None
        if temp[0] == self.personal_list_folder_name or temp[0] == self.personal_command_folder_name:
            # raise Exception(f'get_config_category: not a personalization config file: {path}')
            category = temp[0]
            
        # print(f'get_config_category: returning {category}')
        return category

    def update_personalizations(self, path: str, flags: Any) -> None:
        """Callback method for updating personalized contexts after changes to associated source files."""
        
        if self.testing:
            print(f'update_personalizations: starting - {path, flags}')
            
        reload = flags.exists
        if reload:
            ctx_path = self.get_context_from_path(path)

            if self.testing:
                print(f'update_personalizations: {ctx_path=}')
                
            if ctx_path.endswith('.talon'):
                self.load_command_personalizations(target_contexts = [ctx_path])
            else:
                self.load_list_personalizations(target_contexts = [ctx_path])
        else:
            self.unload_personalizations(target_paths = [path])
            
    def reload_config(self, path: str, flags: Any) -> None:
        """Callback method for updating personalized contexts after changes to personalization configuration files."""
        if self.testing:
            print(f'reload_config: starting - {path, flags}')

            # watched_paths = self._get_watched_paths_for_method(self.reload_config)
            # matching_paths = [p for p in watched_paths if p == path]
            # print(f'reload_config: TESTING: {len(watched_paths), len(matching_paths)}')

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

    def _get_watched_paths_for_method(self, method: Callable):
        """Internal method returning list of watched paths associated with given callback method."""
        path_to_callback_map = dict({k: v[0][0] for k,v in fs.tree.walk()})
        paths = [k for k,v in path_to_callback_map.items() if v == method]
        return paths

def on_ready() -> None:
    """Callback method for updating personalizations."""

    personalizer.load_personalizations()

    # catch updates
    settings.register("", personalizer.refresh_settings)
        
personalizer = Personalizer()

app.register("ready", on_ready)
