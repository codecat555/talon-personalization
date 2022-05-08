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

# Issues
#
# 1. STALE DATA
# 
# When a source file (as opposed to a config file) is updated, Talon calls the registered
# callback - _update_personalizations(). That callback unloads the context and then reloads
# the data from the registry (e.g. in load_one_command_context()).
# 
# However, sometimes the Talon registry is out of date, and so the source file changes are not
# reflected in the resulting personalized context.
#
# Note: Talon does invoke the callback multiple times, and this code checks the file mtime
# to know whether to actually reload or not. So, perhaps we need to keep reloading every
# time Talon tells us to until we get it right...?
# 
# Nope - just tried that - I changed _is_modified() to always return True, and the debug output
# showed the reload did occur multiple times. However, the registry returned stale values in all
# cases.
#
# OH - looks like Talon invokes the callback here BEFORE updating the file itself. That means we
# can't use Talon's file monitoring to do what we want.
#
# Here is some example output. In the second-to-last line, you can see a value of '200ms' in the 
# command definition. I had just manually changed that value to '300ms' and that is what triggered
# this event.
#
# 2022-05-05 23:17:12 DEBUG update_personalizations: starting - ('C:\\Users\\me\\AppData\\Roaming\\talon\\user\\knausj_talon\\misc\\testfile.talon', FsEventFlags(exists=True, renamed=False))
# 2022-05-05 23:17:12 DEBUG update_personalizations: ctx_path='user.knausj_talon.misc.testfile.talon'
# 2022-05-05 23:17:12 DEBUG unload_personalizations: processing target path - C:\Users\me\AppData\Roaming\talon\user\knausj_talon\misc\testfile.talon, user.knausj_talon.misc.testfile.talon
# 2022-05-05 23:17:12 DEBUG unload_personalizations: target context is known - user.knausj_talon.misc.testfile.talon
# 2022-05-05 23:17:12 DEBUG unload_personalizations: is_matching_ctx=None
# 2022-05-05 23:17:12 DEBUG unload_personalizations: unloading context user.knausj_talon.misc.testfile.talon (C:\Users\me\AppData\Roaming\talon\user\knausj_talon\misc\testfile.talon)
# 2022-05-05 23:17:12 DEBUG _unwatch: _update_personalizations, knausj_talon\misc\testfile.talon
# 2022-05-05 23:17:12 DEBUG _split_context_to_user_path_and_file_name: context_path='user.knausj_talon.misc.testfile.talon'
# 2022-05-05 23:17:12 DEBUG load_command_personalizations: loading customizations from "C:\Users\me\AppData\Roaming\talon\user\personalization\config\command_personalization\control.csv"...
# 2022-05-05 23:17:12 DEBUG _is_config_file: returning is_file=False, is_config=False, result=False
# 2022-05-05 23:17:12 DEBUG _is_config_file: returning is_file=True, is_config=False, result=False
# 2022-05-05 23:17:12 DEBUG _is_config_file: returning is_file=True, is_config=False, result=False
# 2022-05-05 23:17:12 DEBUG _is_config_file: returning is_file=True, is_config=False, result=False
# 2022-05-05 23:17:12 DEBUG _is_config_file: returning is_file=True, is_config=True, result=True
# 2022-05-05 23:17:12 DEBUG _unwatch: _update_config, command_personalization\control.csv
# 2022-05-05 23:17:12 DEBUG _is_config_file: returning is_file=True, is_config=True, result=True
# 2022-05-05 23:17:12 DEBUG _unwatch: _update_config, command_personalization\testfile_deletions.csv
# 2022-05-05 23:17:12 DEBUG _is_config_file: returning is_file=True, is_config=True, result=True
# 2022-05-05 23:17:12 DEBUG _unwatch: _update_config, command_personalization\testfile_deletions1.csv
# 2022-05-05 23:17:12 DEBUG _is_config_file: returning is_file=True, is_config=True, result=True
# 2022-05-05 23:17:12 DEBUG _unwatch: _update_config, command_personalization\testfile_replacements.csv
# 2022-05-05 23:17:12 DEBUG _is_config_file: returning is_file=True, is_config=True, result=True
# 2022-05-05 23:17:12 DEBUG _unwatch: _update_config, command_personalization\testfile_additions.csv
# 2022-05-05 23:17:12 DEBUG load_command_personalizations: at line 1 - ('user.knausj_talon.misc.testfile.talon', 'DELETE', 'testfile_deletions.csv')
# 2022-05-05 23:17:12 DEBUG load_one_command_context: using registry command set
# 2022-05-05 23:17:12 DEBUG load_one_command_context: commands={'testphrase one': 'key(alt-tab)\nsleep(200ms)\nkey(alt-tab)\n', 'test delete one': "'test delete one'", 'test delete two': "'test delete two'", 'test delete three': "'test delete three'"}
# 2022-05-05 23:17:12 DEBUG _split_context_to_user_path_and_file_name: context_path='user.knausj_talon.misc.testfile.talon'
#
#

import os
from threading import RLock
from pathlib import Path
import csv
import pprint
from shutil import rmtree
from typing import Any, List, Dict, Union, Tuple, Callable
import logging
from io import IOBase
import atexit

from talon import Context, registry, app, Module, settings, actions, fs

class LoadError(Exception):
    pass

class ItemCountError(Exception):
    pass

class FilenameError(Exception):
    pass

# make sure file watches are released
def atexit():
    if p:
        if p.testing:
            logging.debug(f'atexit: destroying Personalizer instance before exiting...')
        del p

class Personalizer():
    
    class PersonalContext():
        def __init__(self, ctx_path: str):
            if not ctx_path in registry.contexts:
                raise Exception(f'__init__: cannot redefine a context that does not exist: "{ctx_path}"')
            self.ctx_path = ctx_path

    class PersonalListContext(PersonalContext):
        def __init__(self, ctx_path: str):
            super().__init__(ctx_path)

            self.lists = {}

        def get_list(self, list_name: str):
            if not list_name in self.lists:
                try:
                    self.lists[list_name] = dict(registry.lists[list_name][0])
                except KeyError as e:
                    raise Exception(f'remove: no such list: {list_name}')

            return self.lists[list_name]
                    
        def remove(self, list_name: str):
            try:
                del self.lists[list_name]
            except KeyError as e:
                raise Exception(f'remove: no such list: {list_name}')
                
        def write(self, f: IOBase):
            pp = pprint.PrettyPrinter(indent=4)
            for list_name, list_value in self.lists.items():
                print(f'ctx.lists["{list_name}"] = {pp.pformat(list_value)}\n', file=f)
                
    class PersonalCommandContext(PersonalContext):
        def __init__(self, ctx_path: str):
            super().__init__(ctx_path)

            # self.commands = {}
            # need to copy this way to avoid KeyErrors (in current Talon versions)
            self.commands = {v.rule.rule:v.target.code for k,v in registry.contexts[self.ctx_path].commands.items()}
        
        # WIP - maybe rename as 'mask'
        def remove(self, command_key: str):
            try:
                # del commands[command_key]
                self.commands[command_key] = 'skip()'
            except KeyError as e:
                raise Exception(f'remove: no such command: {command_key}')
                
        def replace(self, command_key: str, new_value: str):
            try:
                self.commands[command_key] = new_value
            except KeyError as e:
                raise Exception(f'remove: no such command: {command_key}')

        def write(self, f: IOBase):
            for personal_command, personal_impl in self.commands.items():
                print(f'{personal_command}:', file=f)
                for line in personal_impl.split('\n'):
                    print(f'\t{line}', file=f)
                
    def __init__(self):
        # this code has multiple event triggers which may overlap. so, we use a mutex to make sure
        # only one copy runs at a time.
        self._personalization_mutex: RLock = RLock()

        self._mod = Module()
        
        self.enable_setting = self._mod.setting(
            "enable_personalization",
            type=bool,
            default=False,
            desc="Whether to enable the personalizations defined by the CSV files in the settings folder.",
        )

        # the tag used to enable/disable personalized contexts
        self.personalization_tag_name = 'personalization'
        self.personalization_tag_name_qualified = 'user.' + self.personalization_tag_name
        self.personalization_tag = self._mod.tag(self.personalization_tag_name, desc='enable personalizations')

        self._ctx = Context()
        self._ctx.matches = f'tag: {self.personalization_tag_name_qualified}'
        
        # structure used to store metadata for all personalized contexts
        self._personalizations: Dict[str, PersonalContext] = {}

        # track modification times of updated files, so we reload only when needed rather than every
        # time Talon invokes the callback.
        # WIP - this could  be implemented as a custom class, so we can transparently
        # WIP - handle both str and Path types as keys, interchangeably. then, we wouldn't
        # WIP - have to be so careful throughout the rest of the code (to avoid mixing them).
        self._updated_paths = {}

        self.control_file_name = 'control.csv'

        # folder where personalized contexts are kept
        self.personal_folder_name = '_personalizations'
        self.personal_folder_path = Path(__file__).parents[1] / self.personal_folder_name
        
        # where config files are stored
        self.personal_config_folder_name = 'config'
        self.personal_config_folder = Path(__file__).parents[1] / self.personal_config_folder_name
        os.makedirs(self.personal_config_folder, mode=550, exist_ok=True)

        # we monitor this folder if the config directory ever disappears, looking for a reappearance
        self.personal_config_folder_parent = self.personal_config_folder.parents[0]

        # config sub folder for list personalizations
        self.personal_list_folder_name = 'list_personalization'
        self.personal_list_control_file_subpath = os.path.join(self.personal_list_folder_name, self.control_file_name)
        self.personal_list_control_file_path = os.path.join(self.personal_config_folder, self.personal_list_folder_name)
        os.makedirs(self.personal_list_control_file_path, mode=550, exist_ok=True)

        # config sub folder for command personalizations
        self.personal_command_folder_name = 'command_personalization'
        self.personal_command_control_file_subpath = os.path.join(self.personal_command_folder_name, self.control_file_name)
        self.personal_command_control_file_path = os.path.join(self.personal_config_folder, self.personal_command_folder_name)
        os.makedirs(self.personal_command_control_file_path, mode=550, exist_ok=True)
        
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

    def __del__(self) -> None:
        #if self.testing:
        #    logging.debug(f'__del__: unloading personalizations on object destruction...')
        # self.unload_personalizations()
        
        if self.testing:
            logging.debug(f'__del__: releasing file watches on object destruction...')

        for method in [self._update_personalizations, self._update_config, self._monitor_config_dir]:
            try:
                self._unwatch_all(method)
            except Exception as e:
                logging.warning(f'__del__: {str(e)}')
    
    def _refresh_settings(self, target_ctx_path: str, new_value: Any) -> None:
        """Callback for handling Talon settings changes"""
        #if self.testing:
        #    logging.debug(f'_refresh_settings: {target_ctx_path=}, {new_value=}')
        if target_ctx_path == self.enable_setting.path:
            if new_value:
                # personalizations have been enabled, load them in
                self.load_personalizations()
            else:
                # personalizations have been disabled, unload them
                # instead, we could just disable the tag here...
                self.unload_personalizations()

    def unload_list_personalizations(self) -> None:
        if self.testing:
            logging.debug(f'unload_list_personalizations: starting...')
            
        self.unload_personalizations(is_matching_ctx=lambda x: not x.endswith('.talon'))

    def unload_command_personalizations(self) -> None:
        if self.testing:
            logging.debug(f'unload_command_personalizations: starting...')

        self.unload_personalizations(is_matching_ctx=lambda x: x.endswith('.talon'))

    def unload_personalizations(self, target_paths: List[str] = None, is_matching_ctx: Callable = None) -> None:
        """Unload some (or all) personalized contexts."""
        with self._personalization_mutex:
            if is_matching_ctx:
                # _get_fs_path_for_context() returns a list of str
                target_paths = [self._get_fs_path_for_context(ctx_path) for ctx_path in self._personalizations]

            if target_paths:
                for file_path in target_paths:
                    ctx_path = self._get_context_from_path(file_path)
                    
                    if self.testing:
                        logging.debug(f'unload_personalizations: processing target path - {file_path}, {ctx_path}')
                        
                    if ctx_path in self._personalizations:
                        if self.testing:
                            logging.debug(f'unload_personalizations: target context is known - {ctx_path}')
                            logging.debug(f'unload_personalizations: {is_matching_ctx=}')
                            
                        if is_matching_ctx:
                            if not is_matching_ctx(ctx_path):
                                if self.testing:
                                    logging.debug(f'unload_personalizations: target context does NOT match, skipping...')
                                continue
                            else:
                                if self.testing:
                                    logging.debug(f'unload_personalizations: target context matches')
                                    
                        if self.testing:
                            logging.debug(f'unload_personalizations: unloading context {ctx_path} ({file_path})')

                        self._unwatch(file_path, self._update_personalizations)
                        self._purge_files([ctx_path])
                        del self._personalizations[ctx_path]
                    else:
                        logging.warning(f'unload_personalizations: skipping unknown context for path "{ctx_path}"')                    
            else:
                if self.testing:
                    logging.debug(f'unload_personalizations: unloading everything...')

                self._personalizations = {}
                self._unwatch_all(self._update_personalizations)
                self._purge_files()

    def _unwatch_all(self, method_ref: Callable) -> None:
        """Internal method to stop watching all watched files associated with given method reference."""

        watched_paths = self._get_watched_paths_for_method(method_ref)
        for p in watched_paths:
            if self.testing:
                logging.debug(f'_unwatch_all: unwatching {p}')
            self._unwatch(p, method_ref)
            
    def _purge_files(self, target_contexts: List[str] = None) -> None:
        """Internal method to remove all files storing personalized contexts."""
        with self._personalization_mutex:
            if target_contexts:
                for ctx_path in target_contexts:
                    path = self._get_fs_path_for_context(ctx_path)
                    sub_path = os.path.relpath(path, actions.path.talon_user())
                    # personal_path is a Path
                    personal_path = self.personal_folder_path / sub_path

                    try:
                        os.remove(personal_path)
                    except FileNotFoundError:
                        pass
            else:
                if os.path.exists(self.personal_folder_path):
                    rmtree(self.personal_folder_path)

    def load_personalizations(self) -> None:
        """Load/unload defined personalizations, based on whether the feature is enabled or not."""
        with self._personalization_mutex:
            if self.enable_setting.get():
                self._ctx.tags = [self.personalization_tag_name_qualified]
                self.load_list_personalizations()
                self.load_command_personalizations()
                self.generate_files()

                # after we have loaded at least once, begin monitoring the config folder for changes. this
                # covers the case where no control files exist at startup but then are added later.
                # print(f'load_personalizations: HERE I AM - {self.personal_config_folder=}')
                self._watch(self.personal_config_folder, self._update_config)
            else:
                self._ctx.tags = []
                self.unload_personalizations()
                return
   
    def load_one_list_context(self, action: str, target_ctx_path: str, target_list_name: List[str], config_file_path: str) -> None:
        """Load a single list context."""
        
        try:
            target_list = self.get_list_personalization(target_ctx_path, target_list_name)
        except KeyError as e:
            raise LoadError(f'load_one_list_context: not found: {str(e)}')

        if action.upper() == 'DELETE':
            deletions = []
            try:
                # load items from config file
                deletions = self._load_count_items_per_row(1, config_file_path)
            except ItemCountError:
                raise LoadError(f'files containing deletions must have just one value per line, skipping entire file: "{config_file_path}"')
                
            except FileNotFoundError:
                raise LoadError(f'missing file for delete entry, skipping: "{config_file_path}"')

            # logging.debug(f'load_one_list_context: {deletions=}')

            for d in deletions:
                del target_list[d[0]]

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
            
            if action.upper() == 'REPLACE':
                target_list.clear()
                
            # logging.debug(f'load_one_list_context: {additions=}')
            
            target_list.update(additions)
        else:
            raise LoadError(f'unknown action, skipping: "{action}"')

        return
        
    def _load_count_items_per_row(self, items_per_row: int, file_path: str) -> List[List[str]]:
        """Internal method to read a CSV file expected to have a fixed number of items per row."""
        items = []
        for row in self._get_config_lines(file_path):
            if len(row) > items_per_row:
                raise ItemCountError()
            items.append(row)

        return items

    def load_list_personalizations(self, target_contexts: List[str] = [], target_config_paths: List[str] = [], updated_contexts: List[str] = None) -> None:
        """Load some (or all) defined list personalizations."""
        
        if target_contexts and target_config_paths:
            raise ValueError('load_list_personalizations: bad arguments - cannot accept both "target_contexts" and "target_config_paths" at the same time.')
            
        if target_contexts:
            if self.testing:
                logging.debug(f'load_list_personalizations: {target_contexts=}')
            
        # use str, not Path
        nominal_control_file = self.personal_config_folder / self.personal_list_control_file_subpath
        control_file = os.path.realpath(nominal_control_file)
        
        if self.testing:
            logging.debug(f'load_list_personalizations: loading customizations from "{control_file}"...')
        
        if target_config_paths and control_file in target_config_paths:
            # if we're reloading the control file, then we're doing everything anyways
            target_config_paths = None

        # unwatch all config files until found again in the loop below
        watched_paths = self._get_watched_paths_for_method(self._update_config)
        for path in watched_paths:
            if self._is_list_config_file(path):
                self._unwatch(path, self._update_config)

        if os.path.exists(control_file):
            self._watch(control_file, self._update_config)
        else:
            # nothing to do, apparently
            return
            
        try:
            # loop through the control file and do the needful
            line_number = 0
            for action, source_file_path, target_list, *remainder in self._get_config_lines(control_file, escapechar=None):
                line_number += 1

                target_ctx_path = self._get_context_from_path(source_file_path)

                # determine the CSV file path, check error cases and establish config file watches
                config_file_path = None
                if len(remainder):
                    # use str, not Path
                    nominal_config_file_path = str(self.personal_config_folder / self.personal_list_folder_name / remainder[0])
                    config_file_path = os.path.realpath(nominal_config_file_path)
                    if os.path.exists(config_file_path):
                        self._watch(config_file_path, self._update_config)
                    else:
                        logging.error(f'load_list_personalizations: file not found for {action.upper()} entry, skipping: "{config_file_path}"')
                        continue
                elif action.upper() != 'REPLACE':
                    logging.error(f'load_list_personalizations: missing file name for {action.upper()} entry, skipping: "{target_list}"')
                    continue

                if target_contexts:
                    # # we are loading some, not all, contexts. see if the current target matches given list.
                    # for ctx_path in target_contexts:
                    if not target_ctx_path in target_contexts:
                        # current target is not in the list of targets, skip
                        if self.testing:
                            logging.debug(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {target_ctx_path} not in given list of target contexts')
                        continue
                    
                if self.testing:
                    logging.debug(f'load_list_personalizations: at line {line_number} - {action, target_ctx_path, target_list, remainder}')

                if target_config_paths:
                    # we are loading some, not all, paths. see if the current path matches our list.
                    # note: this does the right thing even when real_config_file_path is None, which is sometimes the case.
                    if config_file_path in target_config_paths:
                        #if self.testing:
                        #    logging.debug(f'load_list_personalizations: loading {real_config_file_path}, because it is in given list of target config paths"')
                        
                        # consume the list as we go so at the end we know if we missed any paths
                        target_config_paths.remove(config_file_path)
                    else:
                        if self.testing:
                            logging.debug(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {config_file_path} is NOT in given list of target config paths.')
                        continue

                if not target_ctx_path in registry.contexts:
                    logging.error(f'load_list_personalizations: cannot redefine a context that does not exist, skipping: "{target_ctx_path}"')
                    continue
                
                # load the target context
                try:
                    self.load_one_list_context(action, target_ctx_path, target_list, config_file_path)
                except FilenameError as e:
                    logging.error(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {str(e)}')
                    continue
                except LoadError as e:
                    logging.error(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {str(e)}')
                    continue

                #if self.testing:
                #    logging.debug(f'load_list_personalizations: AFTER {action.upper()}, {value=}')

                # make sure we are monitoring the source file for changes
                self._watch_source_file_for_context(target_ctx_path, self._update_personalizations)

                if not updated_contexts is None:
                    updated_contexts.add(target_ctx_path)
        
        except FileNotFoundError as e:
            # below check is necessary because the inner try blocks above do not catch this error
            # completely...something's odd about the way talon is handling these exceptions.
            logging.warning(f'load_list_personalizations: setting "{self.setting_enable_personalization.path}" is enabled, but personalization config file does not exist: "{e.filename}"')

    def _watch_source_file_for_context(self, ctx_path: str, method_ref: Callable) -> None:
        """Internal method to watch the file associated with a given context."""
        watch_path = self._get_fs_path_for_context(ctx_path)
        self._watch(watch_path, method_ref)

    def _get_fs_path_for_context(self, ctx_path: str) -> str:
        """Convert given Talon context path into the equivalent filesystem path."""
        path_prefix, filename = self._split_context_to_user_path_and_file_name(ctx_path)
        path = os.path.join(actions.path.talon_user(), path_prefix, filename)
        
        if not ctx_path.endswith('.talon'):
            path = path + '.py'

        return path

    def _get_short_path(self, path: str) -> str:
        short_path = Path(path)
        if short_path.is_relative_to(os.path.realpath(self.personal_config_folder)):
            
            short_path = short_path.relative_to(os.path.realpath(self.personal_config_folder))
        else:
            short_path = short_path.relative_to(os.path.realpath(actions.path.talon_user()))
        
        # return str, not Path
        return str(short_path)

    def _watch(self, path_in: str, method_ref: Callable) -> None:
        """Internal wrapper method to set a file watch."""
        
        # follow symlinks before watching/unwatching
        path = os.path.realpath(path_in)
        
        watched_paths = self._get_watched_paths_for_method(method_ref)
        if path not in watched_paths:
            # if self.testing:
            #     short_path = self._get_short_path(path)
            #
            #     method_name = str(method_ref)
            #     if hasattr(method_ref, '__name__'):
            #         method_name = method_ref.__name__
            #     logging.debug(f'_watch: {method_name}, {short_path}')

            fs.watch(path, method_ref)

    def _unwatch(self, path_in: str, method_ref: Callable) -> None:
        """Internal wrapper method to clear (unset) a file watch."""
        
        # follow symlinks before watching/unwatching
        path = os.path.realpath(path_in)
        
        # if self.testing:
        #     short_path = self._get_short_path(path)
        #
        #     method_name = str(method_ref)
        #     if hasattr(method_ref, '__name__'):
        #         method_name = method_ref.__name__
        #
        #     logging.debug(f'_unwatch: {method_name}, {short_path}')

        try:
            fs.unwatch(path, method_ref)
        except FileNotFoundError:
            # if a file disappears before we can unwatch it, we don't really care
            pass

    def load_one_command_context(self, action: str, target_ctx_path : str, config_file_path : str) -> None:
        """Load a single command context."""

        try:
            commands = self.get_command_personalizations(target_ctx_path)
        except KeyError as e:
            raise LoadError(f'load_one_command_context: not found: {str(e)}')

        if self.testing:
            logging.debug(f'load_one_command_context: {commands.commands=}')

        if action.upper() == 'DELETE':
            deletions = []
            try:
                # load items from source file
                deletions = self._load_count_items_per_row(1, config_file_path)
            except ItemCountError:
                raise LoadError(f'files containing deletions must have just one value per line, skipping entire file: "{config_file_path}"')
            except FileNotFoundError:
                raise LoadError(f'missing file for delete entry, skipping: "{config_file_path}"')

            #if self.testing:
            #    logging.debug(f'load_one_command_context: {deletions=}')

            for row in deletions:
                k = row[0]
                commands.remove(k)
            
        elif action.upper() == 'REPLACE':
            try:
                # load items from source file
                for row in self._load_count_items_per_row(2, config_file_path):
                    target_command = row[0]
                    replacement_command = row[1]

                    try:
                        # fetch the command implementation from Talon
                        impl = registry.contexts[target_ctx_path].commands[target_command].target.code
                    except KeyError as e:
                        raise LoadError(f'cannot replace a command that does not exist, skipping: "{target_command}"')
                    
                    # record changes
                    commands.remove(target_command)
                    commands.replace(replacement_command, impl)
            except ItemCountError:
                raise LoadError(f'files containing additions must have just two values per line, skipping entire file: "{config_file_path}"')
            except FileNotFoundError:
                raise LoadError(f'missing file for add or replace entry, skipping: "{config_file_path}"')
            
        else:
            raise LoadError(f'unknown action, skipping: "{action}"')

        #if self.testing:
        #    logging.debug(f'load_one_command_context: AFTER {action.upper()}, {commands=}')
        
        return

    def load_command_personalizations(self, target_contexts: List[str] = [], target_config_paths: List[str] = [], updated_contexts=None) -> None:
        """Load some (or all) defined command personalizations."""

        if target_contexts and target_config_paths:
            raise ValueError('load_command_personalizations: bad arguments - cannot accept both "target_contexts" and "target_config_paths" at the same time.')

        # use str, not Path
        nominal_control_file = self.personal_config_folder / self.personal_command_control_file_subpath
        real_control_file = os.path.realpath(nominal_control_file)

        if self.testing:
            logging.debug(f'load_command_personalizations: loading customizations from "{real_control_file}"...')
        
        if target_config_paths and real_control_file in target_config_paths:
            # if we're reloading the control file, then we're doing everything anyways
            target_config_paths = None
            
        # unwatch all config files until found again in the loop below
        watched_paths = self._get_watched_paths_for_method(self._update_config)
        for path in watched_paths:
            if self._is_command_config_file(path):
                self._unwatch(path, self._update_config)

        if os.path.exists(real_control_file):
            self._watch(real_control_file, self._update_config)
        else:
            # nothing to do, apparently
            return
            
        try:
            # loop through the control file and do the needful
            line_number = 0
            for action, source_file_path, config_file_name in self._get_config_lines(real_control_file, escapechar=None):
                line_number += 1

                target_ctx_path = self._get_context_from_path(source_file_path)

                # determine the CSV file path, check error cases and establish config file watches
                # use str, not Path

                nominal_config_file_path = str(self.personal_config_folder / self.personal_command_folder_name / config_file_name)
                config_file_path = os.path.realpath(nominal_config_file_path)
                if os.path.exists(config_file_path):
                    self._watch(config_file_path, self._update_config)
                else:
                    logging.error(f'load_command_personalizations: {nominal_control_file}, at line {line_number} - file not found for {action.upper()} entry, skipping: "{config_file_path}"')
                    continue
                
                if self.testing:
                    logging.debug(f'load_command_personalizations: at line {line_number} - {target_ctx_path, action, config_file_name}')

                if target_contexts and not target_ctx_path in target_contexts:
                    # current target is not in the list of targets, skip
                    if self.testing:
                        logging.debug(f'load_command_personalizations: {nominal_control_file}, SKIPPING at line {line_number} - {target_ctx_path} not in list of target contexts')
                    continue

                if target_config_paths:
                    if config_file_path in target_config_paths:
                        # consume the list as we go so at the end we know if we missed any paths
                        target_config_paths.remove(config_file_path)
                    else:
                        if self.testing:
                            logging.debug(f'load_command_personalizations: {nominal_control_file}, SKIPPING at line {line_number} - {config_file_path} is NOT in given list of target config paths')
                        continue

                if not target_ctx_path in registry.contexts:
                    logging.error(f'load_command_personalizations: {nominal_control_file}, at line {line_number} - cannot personalize commands for a context that does not exist, skipping: "{target_ctx_path}"')
                    continue

                value = None
                try:
                    value = self.load_one_command_context(action, target_ctx_path, config_file_path)
                except LoadError as e:
                    logging.error(f'load_command_personalizations: {nominal_control_file}, at line {line_number} - {str(e)}')
                    continue

                self._watch_source_file_for_context(target_ctx_path, self._update_personalizations)

                if not updated_contexts is None:
                    updated_contexts.add(target_ctx_path)

        except (FilenameError, LoadError) as e:
            logging.error(f'load_command_personalizations: {nominal_control_file}, at line {line_number} - {str(e)}')
        except FileNotFoundError as e:
            # this block is necessary because the inner try blocks above do not catch this error
            # completely ...something's odd about the way talon is handling these exceptions.
            logging.warning(f'load_command_personalizations: setting "{self.setting_enable_personalization.path}" is enabled, but personalization config file does not exist: "{e.filename}"')
            
        if target_config_paths:
            logging.error(f'load_command_personalizations: failed to process some targeted config paths: "{target_config_paths}"')

    def _add_tag_to_match_string(self, old_match_string: str, tag: str = None) -> str:
        """Internal function to add personalization tag to given match string."""
        if tag is None:
            tag = self.tag_expression

        new_match_string: str = old_match_string + tag

        #if self.testing:
        #    logging.debug(f'_add_tag_to_match_string: {old_match_string=}, {new_match_string=}')
        return new_match_string

    def _split_context_to_user_path_and_file_name(self, context_path: str) -> Tuple[str, str]:
        """Internal function for extracting filesystem path information from Talon context path."""
        
        # if self.testing:
        #    logging.debug(f'_split_context_to_user_path_and_file_name: {context_path=}')
        
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
            raise Exception('_split_context_to_user_path_and_file_name: cannot override non-user paths at this time')

        user_path = os.path.sep.join(user_path[start_idx:filename_idx])
        
        #if self.testing:
        #    logging.debug(f'_split_context_to_user_path_and_file_name: got {context_path}, returning {wip, filename}')

        return user_path, filename

    def _write_py_header(self, f: IOBase, context_path: str) -> None:
        """Internal method for writing header to Talon python file."""
        header = self.personalized_header.format(context_path, self.personal_folder_name)
        print(header, file=f)

    def _write_py_context(self, f: IOBase, match_string: str) -> None:
        """Internal method for writing context definition to Talon python file."""
        print('from talon import Context', file=f)
        print('ctx = Context()', file=f)
        print(f'ctx.matches = """{match_string}"""\n', file=f)

    def _write_talon_header(self, f: IOBase, context_path: str) -> None:
        """Internal method for writing header to .talon file."""
        header = self.personalized_header.format(context_path, self.personal_folder_name)
        print(header, file=f)

    def _write_talon_context(self, f: IOBase, match_string: str) -> None:
        """Internal method for writing context definition to .talon file."""
        print(f'{match_string}\n-', file=f)
        
    def _write_talon_tag_calls(self, f: IOBase, context_path: str) -> None:
        """Internal method for writing tag calls to .talon file."""
        for line in self._get_tag_calls(context_path):
            print(line, file=f, end='')
        print(file=f)

    def generate_files(self, target_contexts: List[str] = None) -> None:
        """Generate personalization files from current metadata."""
        if self.testing:
            logging.debug(f'generate_files: writing customizations to "{self.personal_folder_path}"...')
        
        self._purge_files(target_contexts=target_contexts)

        if not target_contexts:
            target_contexts = self._personalizations.keys()
            
        for ctx_path in target_contexts:
            # logging.debug(f'generate_files: {ctx_path=}')

            filepath_prefix = self.get_personal_filepath_prefix(ctx_path)
            # logging.debug(f'generate_files: {filepath_prefix=}')
            
            source_match_string = self._get_source_match_string(ctx_path)
            # logging.debug(f'generate_files: {source_match_string=}')
            
            self.write_one_file(ctx_path, filepath_prefix, source_match_string)

    def write_one_file(self, ctx_path: str, file_path: str, source_match_string: str) -> None:
        """Generate one personalized file"""
        new_match_string = self._add_tag_to_match_string(source_match_string)

        # logging.debug(f'write_one_file: {ctx_path=}, {new_match_string=}')

        if ctx_path.endswith('.talon'):
            command_personalizations = self.get_command_personalizations(ctx_path)

            if self.testing:
                logging.debug(f'update_one_file: writing command customizations to "{file_path}"...')
                
            with open(file_path, 'w') as f:
                self._write_talon_header(f, ctx_path)
                    
                self._write_talon_context(f, new_match_string)
                    
                self._write_talon_tag_calls(f, ctx_path)
                    
                # logging.debug(f'write_one_file: {command_personalizations=}')
                command_personalizations.write(f)

        else:
            list_personalizations = self.get_list_personalizations(ctx_path)
            file_path = file_path + '.py'

            if self.testing:
                logging.debug(f'write_one_file: writing list customizations to "{file_path}"...')
                
            with open(file_path, 'w') as f:
                self._write_py_header(f, ctx_path)
                self._write_py_context(f, new_match_string)
                list_personalizations.write(f)

    def _get_source_match_string(self, context_path: str) -> str:
        """Return context match string for given context."""

        context_personalizations = self.get_personalizations(context_path)
        if 'source_context_match_string' in context_personalizations:
            source_match_string = context_personalizations['source_context_match_string']
        else:
            source_match_string, _ = self._load_matches_and_tags(context_path)
            
        return source_match_string
    
    def _get_tag_calls(self, context_path: str) -> List[str]:
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
            context = self._get_source_context(context_path)
            source_match_string = context.matches

        context_personalizations = self.get_personalizations(context_path)
        context_personalizations['source_context_match_string'] = source_match_string
        context_personalizations['tag_calls'] = tag_calls
        
        # logging.debug(f'_load_matches_and_tags: returning {source_match_string=}, {tag_calls=}')

        return source_match_string, tag_calls

    def _parse_talon_file(self, ctx_path: str) -> Union[str, List[str]]:
        """Internal method to extract match string and tags from the source file for a given context."""
        path_prefix, filename = self._split_context_to_user_path_and_file_name(ctx_path)
        file_path = os.path.join(actions.path.talon_user(), path_prefix, filename)
        
        # logging.debug(f'_parse_talon_file: for {ctx_path}, file is {filepath_prefix}')
        
        source_match_string = ''
        tag_calls = []
        with open(file_path, 'r') as f:
            seen_dash = False
            for line in f:
                if seen_dash:
                    if line.strip().startswith('tag():'):
                        # filter out personalization tag here, or error...?
                        tag_calls.append(line)
                else:
                    if line.startswith('-'):
                        seen_dash = True
                    elif line.lstrip().startswith('#'):
                        continue
                    else:
                        # logging.debug(f'_parse_talon_file: found context match line: {line}')
                        source_match_string += line
            if not seen_dash:
                # never found a '-' => no context header for this file
                source_match_string = ''
        
        # logging.debug(f'_parse_talon_file: for {ctx_path}, returning {source_match_string=}, {tag_calls=}')
        
        return source_match_string, tag_calls

    def get_personal_filepath_prefix(self, context_path: str) -> str:
        """Return the personalized file path for the given context"""
        path_prefix, filename = self._split_context_to_user_path_and_file_name(context_path)
        path = self.personal_folder_path / path_prefix
        if not os.path.exists(path):
            os.makedirs(path, mode=550, exist_ok=True)
            
        filepath_prefix = path / filename

        # use str, not Path
        return str(filepath_prefix)

    def get_personalizations(self, context_path: str) -> Dict:
        """Return personalizations for given context path"""
        if not context_path in self._personalizations:
            self._personalizations[context_path] = {}

        return self._personalizations[context_path]

    def _get_source_context(self, context_path: str) -> Dict:
        """Return Talon context reference for given context path."""
        context_personalizations = self.get_personalizations(context_path)

        if not 'source_context' in context_personalizations:
            context_personalizations['source_context'] = registry.contexts[context_path]

        return context_personalizations['source_context']
        
    def get_list_personalizations(self, context_path: str) -> Dict:
        """Return list personalizations for given context path"""
        context_personalizations = self.get_personalizations(context_path)

        if not 'lists' in context_personalizations:
            context_personalizations['lists'] = self.PersonalListContext(context_path)
            
        return context_personalizations['lists']

    def get_list_personalization(self, ctx_path: str, list_name: str) -> PersonalListContext:
        list_personalizations = self.get_list_personalizations(ctx_path)
        return list_personalizations.get_list(list_name)

    def get_command_personalizations(self, context_path: str) -> Dict:
        """Returned command personalizations for given context path"""
        context_personalizations = self.get_personalizations(context_path)

        if not 'commands' in context_personalizations:
            context_personalizations['commands'] = self.PersonalCommandContext(context_path)
            
        return context_personalizations['commands']

    def _get_config_lines(self, path_string: str, escapechar: str ='\\') -> List[List[str]]:
        """Retrieves contents of config file in personalization config folder."""
        
        return self._get_lines_from_csv(path_string, escapechar)
        
    def _get_lines_from_csv(self, path_string: str, escapechar: str ='\\') -> List[List[str]]:
        """Retrieves contents of CSV file in personalization config folder."""
        
        path = Path(os.path.realpath(path_string))
        
        personal_config_folder = os.path.realpath(self.personal_config_folder)
        if not path.is_relative_to(personal_config_folder):
            # logging.debug(f'{path.parents[:]}')
            # msg = f'get_lines_from_csv: file must be in the config folder, {personal_config_folder}, skipping: {path}'
            msg = f'get_lines_from_csv: file must be in the config folder, {self.personal_config_folder}, skipping: {path_string}'
            raise Exception(msg)

        if not path.suffix == ".csv":
            raise FilenameError(f'get_lines_from_csv: file name must end in ".csv", skipping: {path}')

        realpath = os.path.realpath(str(path))

        # print(f'_get_lines_from_csv: {path} -> {realpath}')

        rows = []
        with open(realpath, "r") as f:
            rows = list(csv.reader(f, escapechar=escapechar))

        # logging.debug(f'_get_lines_from_csv: returning {rows}')
        return rows

    def _get_context_from_path(self, path_in: str) -> str:
        """Returns Talon context path corresponding to given talon user folder path."""
        path = Path(path_in)
        if path.is_absolute():
            if not path.is_relative_to(actions.path.talon_user()):
                raise Exception(f'oh no')
        else:
            # assume path is relative to talon user folder
            path = actions.path.talon_user() / path

        # relpath() accepts Path or str, returns str
        temp = os.path.relpath(path, actions.path.talon_user())

        extension = path.suffix
        if not extension == '.talon':
            # remove the file extension. splitext() returns str
            temp, _ = os.path.splitext(temp)
        ctx_path = temp.replace(os.path.sep, '.')

        # this will need to change if we ever want to override any context not under 'user.'.
        return 'user.' + ctx_path

    def _is_list_config_file(self, path: str) -> bool:
        """Checks whether given path is under the list personalization config folder."""
        return self._is_config_file(path, self.personal_list_folder_name)

    def _is_command_config_file(self, path: str) -> bool:
        """Checks whether given path is under the command personalization config folder."""
        return self._is_config_file(path, self.personal_command_folder_name)
    
    def _is_config_file(self, path: str, category: str):
        """Checks whether given path is under the indicated personalization config folder."""
        # logging.debug(f'_is_config_file: starting - {path, category}')

        # is_file() does not work if the file does not exist (i.e. has been deleted)
        # is_file = Path(path).is_file()

        # just look for a suffix - doesn't work on files with no suffix.
        is_file = len(Path(path).suffix) != 0

        is_config = (category == 'control' or category == self._get_config_category(path))
        
        result = is_file and is_config
        
        # if self.testing:
        #     logging.debug(f'_is_config_file: returning {is_file=}, {is_config=}, {result=}')
        
        return result
    
    def _get_config_category(self, path: str) -> str:
        """Return parent directory name of given path relative to the personalization configuration folder, e.g. list_personalization"""
        realpath = os.path.realpath(path)
        personal_config_folder = os.path.realpath(self.personal_config_folder)
        
        temp = os.path.relpath(realpath, personal_config_folder)
        temp = temp.split(os.path.sep)

        category = None
        if temp[0] == self.personal_list_folder_name or temp[0] == self.personal_command_folder_name:
            # raise Exception(f'get_config_category: not a personalization config file: {path}')
            category = temp[0]
        elif temp[0] == self.control_file_name:
            category = 'control'
            
        # logging.debug(f'_get_config_category: returning {category}')
        return category

    def _update_personalizations(self, path: str, flags: Any) -> None:
        """Callback method for updating personalized contexts after changes to associated source files."""
        
        if self.testing:
            logging.debug(f'_update_personalizations: starting - {path, flags}')
            
        reload = flags.exists
        if reload:
            # WIP - reload as many times as Talon tells us to, regardless of whether the
            # WIP - file is actually modified or not.
            # if True or self._is_modified(path):
            if self._is_modified(path):
                ctx_path = self._get_context_from_path(path)

                if self.testing:
                    logging.debug(f'_update_personalizations: {ctx_path=}')
                    
                if ctx_path.endswith('.talon'):
                    self.unload_personalizations(target_paths = [path])
                    self.load_command_personalizations(target_contexts = [ctx_path])
                else:
                    self.unload_personalizations(target_paths = [path])
                    self.load_list_personalizations(target_contexts = [ctx_path])

                self.generate_files(target_contexts=[ctx_path])
        else:
            self.unload_personalizations(target_paths = [path])

    def _monitor_config_dir(self, path: str, flags: Any) -> None:
        """Callback method for responding to config folder re-creation after deletion."""
        
        if self.testing:
            logging.debug(f'_monitor_config_dir: starting - {path, flags}')

        real_personal_config_folder = os.path.realpath(self.personal_config_folder)
        if Path(path) == real_personal_config_folder and flags.exists:
            # config folder has reappeared, stop watching the parent folder and begin
            # watching the config folder again.
            self._unwatch(self.personal_config_folder_parent, self._monitor_config_dir)
            self._watch(self.personal_config_folder, self._update_config)
            
    def _update_config(self, path: str, flags: Any) -> None:
        """Callback method for updating personalized contexts after changes to personalization configuration files."""
        if self.testing:
            logging.debug(f'_update_config: STARTING - {path, flags}')

        # WIP - reload as many times as Talon tells us to, regardless of whether the
        # WIP - file is actually modified or not.
        # modified = True or self._is_modified(path)
        modified = self._is_modified(path)
        if not modified:
            return

        if not flags.exists:
            logging.debug(f'_update_config: cleaning up old config')
            # stop watching files after they've been deleted
            self._unwatch(path, self._update_config)
            
            real_personal_config_folder = os.path.realpath(self.personal_config_folder)            
            if Path(path) == real_personal_config_folder:
                # wait for config folder to reappear
                self._watch(self.personal_config_folder_parent, self._monitor_config_dir)
            
        if len(Path(path).suffix) == 0:
            # ignore directory change notifications
            if self.testing:
                logging.debug(f'_update_config: path is a directory, skip it.')
            return

        # when a config file changes, we can't know what contexts need to be loaded/unloaded without
        # reading the config files again...so, we just reload.
        updated_contexts = set()
        if modified:
            if self._is_list_config_file(path):
                self.unload_list_personalizations()
                self.load_list_personalizations(updated_contexts=updated_contexts)
            elif self._is_command_config_file(path):
                self.unload_command_personalizations()
                self.load_command_personalizations(updated_contexts=updated_contexts)
            else:
                raise Exception(f'_update_config: unrecognized file: {path}')

            if self.testing:
                logging.debug(f'_update_config: AFTER UPDATE: {updated_contexts=}')
                logging.debug(f'_update_config: AFTER UPDATE: {self._updated_paths[path]=}')
                
            self.generate_files(target_contexts=[*updated_contexts])
        else:
            if self.testing:
                logging.debug(f'_update_config: path is not modified, skip it.')

    def _is_modified(self, path: str) -> bool:
        mtime = None
        try:
            mtime = os.stat(path).st_mtime
        except FileNotFoundError as e:
            mtime = 0

        if self.testing:
            logging.debug(f'_is_modified: current timestamp: {mtime}')

        if path in self._updated_paths:
            if self.testing:
                logging.debug(f'_is_modified: path is known with timestamp {self._updated_paths[path]}.')
                
            # WIP - sometimes the file timestamp changes between one invocation of this method and the next, even
            # WIP - though the file has not actually been changed. not sure why this is happening. An example -
            # WIP -
            # WIP - First time callback invoked after adding command config file - testfile_additions.csv. Note that ADD is
            # WIP - not supported for command customization, but that is beside the point. The odd thing here is that the
            # WIP - timestamp changes when I know the file was not actually modified during this (brief) period.
            # WIP - 
            # WIP - 2022-05-05 11:45:06 DEBUG _update_config: STARTING - ('C:\\Users\\xxx\\AppData\\Roaming\\talon\\user\\personalization\\config\\command_personalization\\testfile_additions.csv', FsEventFlags(exists=True, renamed=False))
            # WIP - 2022-05-05 11:45:06 DEBUG _is_modified: current timestamp: 1651776306.2653105
            # WIP - 2022-05-05 11:45:06 DEBUG _is_modified: path is NOT known, record mtime.
            # WIP - ...
            # WIP - 
            # WIP - Second time callback invoked - the timestamp has changed and so the load ran again instead of skipping.
            # WIP - 
            # WIP - 2022-05-05 11:45:06 DEBUG _update_config: STARTING - ('C:\\Users\\xxx\\AppData\\Roaming\\talon\\user\\personalization\\config\\command_personalization\\testfile_additions.csv', FsEventFlags(exists=True, renamed=False))
            # WIP - 2022-05-05 11:45:06    IO _update_config: BEFORE CHECK: self._updated_paths[path]=1651776306.2653105
            # WIP - 2022-05-05 11:45:06 DEBUG _is_modified: current timestamp: 1651776306.269302
            # WIP - 2022-05-05 11:45:06 DEBUG _is_modified: path is known with timestamp 1651776306.2653105.
            # WIP - 2022-05-05 11:45:06 DEBUG _is_modified: path is modified, update mtime.
            # WIP - ...
            # WIP - 
            # WIP - Third time callback invoked - this time the timestamp is stable and so the load was skipped instead of running
            # WIP - a third time (which implies the code here does the right thing when the data is accurate).
            # WIP - 
            # WIP - 2022-05-05 11:45:06 DEBUG _update_config: STARTING - ('C:\\Users\\xxx\\AppData\\Roaming\\talon\\user\\personalization\\config\\command_personalization\\testfile_additions.csv', FsEventFlags(exists=True, renamed=False))
            # WIP - 2022-05-05 11:45:06    IO _update_config: BEFORE CHECK: self._updated_paths[path]=1651776306.269302
            # WIP - 2022-05-05 11:45:06 DEBUG _is_modified: current timestamp: 1651776306.269302
            # WIP - 2022-05-05 11:45:06 DEBUG _is_modified: path is known with timestamp 1651776306.269302.
            # WIP - 2022-05-05 11:45:06 DEBUG _update_config: path is not modified, skip it.
            # WIP - 2022-05-05 11:45:06 DEBUG [~] C:\Users\xxx\AppData\Roaming\talon\user\personalization\_personalizations\knausj_talon\misc\testfile.talon
            #
            if self._updated_paths[path] == mtime:
                return False
            else:
                if self.testing:
                    logging.debug(f'_is_modified: path is modified, update mtime.')
                pass
        else:
            if self.testing:
                logging.debug(f'_is_modified: path is NOT known, record mtime.')
            pass

        self._updated_paths[path] = mtime

        return True
            
    def _get_watched_paths_for_method(self, method: Callable) -> List[str]:
        """Internal method returning list of watched paths associated with given callback method."""
        path_to_callback_map = dict({k: v[0][0] for k,v in fs.tree.walk()})
        paths = [k for k,v in path_to_callback_map.items() if v == method]
        return paths

def on_ready() -> None:
    """Callback method for updating personalizations."""

    personalizer.load_personalizations()

    # catch updates
    settings.register("", personalizer._refresh_settings)
        
personalizer = Personalizer()

app.register("ready", on_ready)
