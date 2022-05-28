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
# UPDATE - looks like this may be a problem only on windows. at least, it seems to be working
# on linux. haven't tested mac.
# 
# When a source file (as opposed to a config file) is updated, Talon calls the registered
# callback - _update_personalizations(). That callback unloads the context and then reloads
# the data from the registry (e.g. in load_one_command_context()).
# 
# However, the Talon registry is still out of date at this point, and so the source file changes
# are not reflected in the resulting personalized context.
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
# Hmmm, looks like the registry provides 'add_context' and 'remove_context' events, maybe those
# will work...Nope, those events also arrive before the registry has been updated.
#

# Note: there can be a problem redefining things that have not yet been defined. this can
# happen if the personalized context gets loaded before the source context (is this documented
# on the basic customization wiki?). Not a problem with this module, since it waits for the ready
# event and the generated personalizations are not enabled until this module switches the tag.

# TODO - fix this:
# 2022-05-21 14:01:39 DEBUG [~] C:\Users\me\AppData\Roaming\talon\user\personalization\settings.talon
# 2022-05-21 14:01:39  INFO Personalizer._update_setting: received updated value for user.verbose_personalization: 0
# 2022-05-21 14:01:39  INFO Personalizer.PersonalContext(user.knausj_talon.code.keys)._update_setting: received updated value for user.verbose_personalization: 0
# 2022-05-21 14:01:39  INFO Personalizer.PersonalContext(user.knausj_talon.text.text_navigation)._update_setting: received updated value for user.verbose_personalization: 0
#
# TODO - need to handle the case where multiple contexts are defined in the same (.py) file...if
# the user wants to override a list in such a file, we need to figure out whether the context is the
# "normal" default one or whether it has a .1, .2, etc. appended. Perhaps important when translating
# paths to context paths...!

import os
from threading import RLock
from pathlib import Path
import csv
import pprint
from shutil import rmtree
from typing import Any, List, Dict, Tuple, Callable
import logging
from io import IOBase
import re

from talon import Context, registry, app, Module, settings, actions, fs

class LoadError(Exception):
    pass

class ItemCountError(Exception):
    pass

class FilenameError(Exception):
    pass

# enable/disable debug messages
# testing = False

mod = Module()
ctx = Context()

enable_setting = mod.setting(
    "enable_personalization",
    type=bool,
    default=False,
    desc="Enable personalizations, process the configuration files and generate personalized files accordingly.",
)

verbose_setting = mod.setting(
    "verbose_personalization",
    type=bool,
    default=False,
    desc="Enable debug messages in the Talon log.",
)

personalization_tag_name = 'personalization'
personalization_tag = mod.tag(personalization_tag_name, desc='enable personalizations')

# we have two mutually exclusive ways of monitoring for updates, neither of them
# really work at this time, unfortunately...
monitor_registry_for_updates = True
# monitor_filesystem_for_updates = not monitor_registry_for_updates
monitor_filesystem_for_updates = False

@mod.action_class
class PersonalizationActions:
    """
    # Commands for controlling this personalization feature.
    """
    def reload_personalizations() -> None:
        "Regenerate personalized contexts from source files."
        personalizer.unload_personalizations()
        personalizer.load_personalizations()

def makedirs(path: str, mode: int, exist_ok: bool) -> None:
    # https://stackoverflow.com/questions/5231901/permission-problems-when-creating-a-dir-with-os-makedirs-in-python
    try:
        original_umask = os.umask(0)
        os.makedirs(path, mode=mode, exist_ok=exist_ok)
    finally:
        os.umask(original_umask)
        
class Personalizer():
    """Generate personalized Talon contexts from source and configuration files."""

    class PersonalContext():
        """A personalized Talon context."""
        
        def __init__(self, ctx_path: str, personalizer: Any, settings_map: Dict):
            if not ctx_path in registry.contexts:
                raise Exception(f'__init__: cannot redefine a context that does not exist: "{ctx_path}"')

            # ref to parent
            self.personalizer: Personalizer = personalizer

            self.ctx_path = ctx_path

            self._testing = None

            self.settings_map = settings_map
            self.refresh_map =  {
                talon_setting.path: local_name
                    for local_name, talon_setting in settings_map.items()
                                                        if hasattr(self, local_name) }

        @property
        def testing(self) -> bool:
            if self._testing is None:
                self._testing = self.settings_map['testing'].get()
            return self._testing

        @testing.setter
        def testing(self, value: bool) -> None:
            self._testing = value

        # update settings
        def refresh_settings(self, args) -> None:
            # if self.testing:
            #     logging.debug(f'Personalizer.PersonalContext.refresh_settings: {args=}')

            caller_id = 'Personalizer.PersonalContext(' + self.ctx_path + ')'
            if args:
                self.personalizer._update_setting(self, caller_id, args)
            else:
                self.personalizer._update_all_settings(self, caller_id)

        def _personalize_match_string(self, tag: str) -> str:
            """Internal function to add personalization tag to the context match string."""

            # this method turned out to be simple enough to omit, but if new cases arise
            # this will be a convenient place for the patch.

            old_match_string: str = self.source_match_string
            new_match_string: str = old_match_string + tag

            #if self.testing:
            #    logging.debug(f'_personalize_match_string: {old_match_string=}, {new_match_string=}')

            return new_match_string
            
            
    class PersonalListContext(PersonalContext):
        """A personalized Talon list context."""

        def __init__(self, ctx_path: str, personalizer: Any, settings_map: Dict):
            super().__init__(ctx_path, personalizer, settings_map)

            self.lists = {}

            self.source_context = registry.contexts[ctx_path]
            self.source_match_string = self.source_context.matches

        def get_list(self, list_name: str) -> Dict[str, str]:
            if not list_name in self.lists:
                try:
                    self.lists[list_name] = dict(registry.lists[list_name][0])
                except KeyError as e:
                    raise Exception(f'get_list: no such list: {list_name}')

                if self.testing:
                   logging.debug(f'get_list: loaded list from registry: {list_name} = {self.lists[list_name]}')

            return self.lists[list_name]
                    
        def remove(self, list_name: str) -> None:
            try:
                del self.lists[list_name]
            except KeyError as e:
                raise Exception(f'remove: no such list: {list_name}')
                
        def write(self, file_path: str, tag: str, header: str) -> None:
            """Generate one personalized file"""

            # logging.debug(f'write: {ctx_path=}, {new_match_string=}')

            if self.testing:
                logging.debug(f'write: writing list customizations to "{file_path}"...')
                
            with open(file_path, 'w') as f:
                self._write_py_header(f, header)
                self._write_py_context(f, tag)
                pp = pprint.PrettyPrinter(indent=4)
                for list_name, list_value in self.lists.items():
                    print(f'ctx.lists["{list_name}"] = {pp.pformat(list_value)}\n', file=f)

        def _write_py_header(self, f: IOBase, header: str) -> None:
            """Internal method for writing header to Talon python file."""
            print(header, file=f)

        def _write_py_context(self, f: IOBase, tag: str) -> None:
            """Internal method for writing context definition to Talon python file."""
            print('from talon import Context', file=f)
            print('ctx = Context()', file=f)
            
            new_match_string = self._personalize_match_string(tag)
            print(f'ctx.matches = """{new_match_string}"""\n', file=f)

        def get_source_file_path(self) -> str:
            """Function for extracting filesystem path information from the context path string."""
            
            if not self.ctx_path.startswith('user.'):
                raise ValueError('get_source_file_path: can only handle user-defined contexts (ctx_path)')
                
            # if self.testing:
            #    logging.debug(f'get_source_file_path: {ctx_path=}')
            
            sub_path = re.sub(r"^user\.", "", self.ctx_path).replace('.', os.path.sep)
            # sub_path = Path(self.ctx_path.replace('.', os.path.sep))
            # parent_path = actions.path.talon_user() / sub_path
            parent_path = actions.path.talon_user() / Path(sub_path)
            
            # logging.debug(f'get_source_file_path: {parent_path=}, {ctx_path=}')
            
            user_path = parent_path.with_suffix('.py')
            
            if self.testing:
                logging.debug(f'PersonalListContext.get_source_file_path: returning {user_path=}')
            
            return user_path

    class PersonalCommandContext(PersonalContext):
        """A personalized Talon command context."""
        
        def __init__(self, ctx_path: str, personalizer: Any, settings_map: Dict):
            super().__init__(ctx_path, personalizer, settings_map)

            if self.testing:
                   logging.debug(f'__init__: loading commands from registry for context {ctx_path}')

            # need to copy this way to avoid KeyErrors (in current Talon versions)
            self.commands = {v.rule.rule:v.target.code for k,v in registry.contexts[self.ctx_path].commands.items()}

            # fetch additional information
            self.source_match_string = self.tag_calls = None
            self._parse_talon_file()
        
        def _parse_talon_file(self) -> None:
            """Internal method to extract match string and tags from the source file for a given context."""
            path = self.get_source_file_path()
            
            # logging.debug(f'_parse_talon_file: {self.ctx_path=}, {path}')
            
            source_match_string = ''
            tag_calls = []
            with open(path, 'r') as f:
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
            
            self.source_match_string = source_match_string
            self.tag_calls = tag_calls

        def remove(self, command_key: str) -> None:
            try:
                # del commands[command_key]
                self.commands[command_key] = 'skip()'
            except KeyError as e:
                raise Exception(f'remove: no such command: {command_key}')
                
        def replace(self, command_key: str, new_value: str) -> None:
            try:
                self.commands[command_key] = new_value
            except KeyError as e:
                raise Exception(f'remove: no such command: {command_key}')

        def write(self, file_path: str, tag: str, header: str) -> None:
            """Generate one personalized file"""

            if self.testing:
                logging.debug(f'write: writing command customizations to "{file_path}"...')
                
            with open(file_path, 'w') as f:
                self._write_talon_header(f, header)
                    
                self._write_talon_context(f, tag)
                    
                self._write_talon_tag_calls(f)
                    
                # logging.debug(f'write: {write=}')
                for personal_command, personal_impl in self.commands.items():
                    print(f'{personal_command}:', file=f)
                    for line in personal_impl.split('\n'):
                        print(f'\t{line}', file=f)

        def _write_talon_header(self, f: IOBase, header: str) -> None:
            """Internal method for writing header to .talon file."""
            print(header, file=f)

        def _write_talon_context(self, f: IOBase, tag: str) -> None:
            """Internal method for writing context definition to .talon file."""
            new_match_string = self._personalize_match_string(tag)
            print(f'{new_match_string}\n-', file=f)
            
        def _write_talon_tag_calls(self, f: IOBase) -> None:
            """Internal method for writing tag calls to .talon file."""
            for line in self.tag_calls:
                print(line, file=f, end='')
            print(file=f)

        def get_source_file_path(self) -> str:
            """Function for extracting filesystem path information from the context path string."""
            
            if not self.ctx_path.startswith('user.'):
                raise ValueError('get_source_file_path: can only handle user-defined contexts (ctx_path)')
                
            # if self.testing:
            #    logging.debug(f'split_context_to_user_path_and_file_name: {ctx_path=}')
            
            sub_path = re.sub(r"^user\.", "", self.ctx_path).replace('.', os.path.sep)
            parent_path = actions.path.talon_user() / Path(sub_path).parents[0]
            
            # logging.debug(f'get_source_file_path: {parent_path=}, {ctx_path=}')
            
            # there is a special case here: when the given context path refers to a file
            # named 'talon.py', as in 'knausj_talon/lang/talon/talon.py'. context a.x.talon
            # could be a/x.talon OR a/x/talon.py.
            
            user_path = parent_path.with_suffix('.talon')
            
            if self.testing:
                logging.debug(f'PersonalCommandContext.get_source_file_path: returning {user_path=}')
            
            return user_path

                
    def __init__(self, mod: Module, ctx: Context, settings_map: Dict, personalization_tag_name: str, personalization_tag: Any):
        # # enable/disable debug messages
        self._testing = None

        self._enabled = None
        
        # this code has multiple event triggers which may overlap. so, we use a mutex to make sure
        # only one copy runs at a time.
        self._personalization_mutex: RLock = RLock()

        # capture args
        self._mod = mod
        self._ctx = ctx        

        # the tag used to enable/disable personalized contexts
        # self.personalization_tag_name = 'personalization'
        self.personalization_tag_name_qualified = 'user.' + personalization_tag_name
        self.personalization_tag = personalization_tag

        # structure used to track all contexts received from config files. these persist even when
        # the referenced contexts are unloaded by Talon.
        self._configured_contexts = set()

        # structure used to store metadata for all personalized contexts. loading populates this
        # structure, unloading depopulates it.
        self._personalizations: Dict[str, Personalizer.PersonalContext] = {}

        # track modification times of updated files, so we reload only when needed rather than every
        # time Talon invokes the callback.
        # WIP - this could be implemented as a custom class, so we could transparently
        # WIP - handle both str and Path types as keys, interchangeably. then, we wouldn't
        # WIP - have to be so careful to avoid mixing them throughout the rest of the code.
        self._updated_paths = {}

        self.control_file_name = 'control.csv'

        # path to the folder where all personalization stuff is kept
        #  this will need to change if this module is ever relocated
        self.personalization_root_folder_path = Path(__file__).parents[1]

        # folder where personalized contexts are kept
        self.personal_folder_name = '_personalizations'
        self.personal_folder_path =  self.personalization_root_folder_path / self.personal_folder_name

        self.personalization_context_path_prefix = self._get_personalization_context_path_prefix()

        # where config files are stored
        self.personal_config_folder_name = 'config'
        self.personal_config_folder = self.personalization_root_folder_path / self.personal_config_folder_name
        makedirs(self.personal_config_folder, mode=0o755, exist_ok=True)

        # we monitor this folder if the config directory ever disappears, looking for a reappearance
        self.personal_config_folder_parent = self.personal_config_folder.parents[0]

        # config sub folder for list personalizations
        self.personal_list_folder_name = 'list_personalization'
        self.personal_list_control_file_subpath = os.path.join(self.personal_list_folder_name, self.control_file_name)
        self.personal_list_control_file_path = os.path.join(self.personal_config_folder, self.personal_list_folder_name)
        makedirs(self.personal_list_control_file_path, mode=0o755, exist_ok=True)

        # config sub folder for command personalizations
        self.personal_command_folder_name = 'command_personalization'
        self.personal_command_control_file_subpath = os.path.join(self.personal_command_folder_name, self.control_file_name)
        self.personal_command_control_file_path = os.path.join(self.personal_config_folder, self.personal_command_folder_name)
        makedirs(self.personal_command_control_file_path, mode=0o755, exist_ok=True)
        
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

        # process settings
        self.settings_map = settings_map
        self.refresh_map =  {
                talon_setting.path: local_name
                            for local_name, talon_setting in settings_map.items()
                                                                if hasattr(self, local_name) }
        self.refresh_settings()
        # catch updates
        settings.register("", self.refresh_settings)

    @property
    def enabled(self) -> bool:
        if self._enabled is None:
            self._enabled = self.settings_map['enabled'].get()
            
        return self._enabled
        
    @enabled.setter
    def enabled(self, value) -> None:
        self._enabled = value

        if self._enabled:
            # personalizations have been enabled, load them in
            self.load_personalizations()
        else:
            # personalizations have been disabled, unload them
            self.unload_personalizations()

    @property
    def testing(self) -> bool:
        if self._testing is None:
            self._testing = self.settings_map['testing'].get()
        return self._testing

    @testing.setter
    def testing(self, value) -> None:
        self._testing = value

    def refresh_settings(self, *args) -> None:
        # if self.testing:
        #     # logging.debug(f'refresh_settings: {self.settings_map=}')
        #     logging.debug(f'Personalizer.refresh_settings: args: {args=}')

        caller_id = 'Personalizer'
        if args:
            Personalizer._update_setting(self, caller_id, args)
        else:
            Personalizer._update_all_settings(self, caller_id)

        for personal_context in self._personalizations.values():
            personal_context.refresh_settings(args)

    @classmethod
    def _update_all_settings(cls, caller, caller_id: str) -> None:
        # fetch all our settings
        for local_name, talon_setting in caller.settings_map.items():
            if hasattr(caller, local_name):
                # if caller.testing:
                #     logging.debug(f'{caller_id}._update_all_settings: DEBUG - {caller=}, {talon_setting}, {local_name=}')

                caller.__setattr__(local_name, talon_setting.get())

            if caller.testing:
                logging.debug(f'{caller_id}._update_all_settings: received updated value for {talon_setting.path}: {getattr(caller, local_name, None)}')

    @classmethod
    def _update_setting(cls, caller, caller_id: str, args):
        # fetch updated settings
        talon_name = args[0]
        local_name = None
        try:
            local_name = caller.refresh_map[talon_name]
        except KeyError:
            # not one of our settings
            return
        else:
            caller.__setattr__(local_name, args[1])
        # finally:
        #     if caller.testing:
        #         logging.debug(f'{caller_id}._update_setting: {caller=}, {talon_name=}, {local_name=}, {type(local_name)=}')

        if caller.testing:
            logging.debug(f'{caller_id}._update_setting: received updated value for {talon_name}: {getattr(caller, local_name, None)}')

    def startup(self) -> None:
        """Load/unload personalizations, based on whether the feature is enabled or not."""
        with self._personalization_mutex:
            if self.enabled:
                self.load_personalizations()
            else:
                self.unload_personalizations()

    def load_personalizations(self) -> None:
        """Load defined personalizations."""
        with self._personalization_mutex:
            self._ctx.tags = [self.personalization_tag_name_qualified]
            self.load_list_personalizations()
            self.load_command_personalizations()
            self.generate_files()

            # after we have loaded at least once, begin monitoring the config folder for changes. this
            # covers the case where no control files exist at startup but then are added later.
            # logging.debug(f'load_personalizations: HERE I AM - {self.personal_config_folder=}')
            self._watch(self.personal_config_folder, self._update_config)

    def _validate_source_file_path(self, source_file_path_in: str) -> Tuple[str, str]:
        """Validate given file path, which is assumed to have been read from a control file
        and which may require some transformation."""

        context_path = None
        source_file_path = None
        if os.path.sep in source_file_path_in:
            # seems to be a 'normal' filepath
            source_file_path = os.path.sep.join([actions.path.talon_user(), source_file_path_in])
            context_path = self._get_context_from_path(source_file_path)
        else:
            # could be a 'normal' file in the top level of the user directory, let's see...
            source_file_path = os.path.sep.join([actions.path.talon_user(), source_file_path_in])
            if not os.path.exists(source_file_path):
                # not a top level file, maybe it's a 'universal', i.e. context, path..
                context_path = source_file_path_in
                if not context_path.startswith('user.'):
                    context_path = 'user.' + context_path

                paths = self.get_source_file_paths(context_path)
                if len(paths) == 0:
                    raise ValueError(f'file corresponding to given path not found: {source_file_path_in}')
                elif len(paths) > 1:
                    # not ready right now to figure out what the right action is for this case, punt for now.
                    raise ValueError(f'given context path yields ambiguous file paths: {source_file_path_in} => {paths}')
                source_file_path = paths[0]

        if Path(source_file_path).is_relative_to(self.personal_folder_path):
            raise ValueError('cannot personalize personalized files')

        return source_file_path, context_path 
        
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

        if not os.path.exists(control_file):
            return
        
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

        self._watch(control_file, self._update_config)
            
        try:
            # loop through the control file and do the needful
            line_number = 0
            for action, source_file_path, target_list_name, *remainder in self._get_config_lines(control_file, escapechar=None):
                line_number += 1

                if self.testing:
                    logging.debug(f'load_list_personalizations: read line {line_number}: {action=}, {source_file_path=}, {target_list_name=}, {remainder}')

                try:
                    source_file_path, target_ctx_path = self._validate_source_file_path(source_file_path)
                except ValueError as e:
                    logging.error(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {str(e)}')
                    continue

                # handle mapping of 'self' to 'user' 
                target_list_name = re.sub(r"^self\.", "user.", target_list_name)

                # determine the CSV file path, check error cases and establish config file watches
                auxiliary_file_path = None
                if len(remainder):
                    # use str, not Path
                    nominal_auxiliary_file_path = str(self.personal_config_folder / self.personal_list_folder_name / remainder[0])
                    auxiliary_file_path = os.path.realpath(nominal_auxiliary_file_path)
                    if os.path.exists(auxiliary_file_path):
                        self._watch(auxiliary_file_path, self._update_config)
                    else:
                        logging.error(f'load_list_personalizations: file not found for {action.upper()} entry, skipping: "{auxiliary_file_path}"')
                        continue
                elif action.upper() != 'REPLACE':
                    logging.error(f'load_list_personalizations: missing file name for {action.upper()} entry, skipping: "{target_list_name}"')
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
                    logging.debug(f'load_list_personalizations: at line {line_number} - {action, target_ctx_path, target_list_name, remainder}')

                if target_config_paths:
                    # we are loading some, not all, paths. see if the current path matches our list.
                    # note: this does the right thing even when real_config_file_path is None, which is sometimes the case.
                    if auxiliary_file_path in target_config_paths:
                        #if self.testing:
                        #    logging.debug(f'load_list_personalizations: loading {real_config_file_path}, because it is in given list of target config paths"')
                        
                        # consume the list as we go so at the end we know if we missed any paths
                        target_config_paths.remove(auxiliary_file_path)
                    else:
                        if self.testing:
                            logging.debug(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {auxiliary_file_path} is NOT in given list of target config paths.')
                        continue

                if not target_ctx_path in registry.contexts:
                    logging.error(f'load_list_personalizations: cannot redefine a context that does not exist, skipping: "{target_ctx_path}"')
                    continue
                
                # load the target context
                try:
                    self.load_one_list_context(action, target_ctx_path, target_list_name, auxiliary_file_path)
                except FilenameError as e:
                    logging.error(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {str(e)}')
                    continue
                except LoadError as e:
                    logging.error(f'load_list_personalizations: {control_file}, SKIPPING at line {line_number} - {str(e)}')
                    continue

                #if self.testing:
                #    logging.debug(f'load_list_personalizations: AFTER {action.upper()}, {value=}')

                # make sure we are monitoring the source file for changes
                if monitor_filesystem_for_updates:
                    self._watch_source_file_for_context(target_ctx_path, self._update_personalizations)

                if not updated_contexts is None:
                    updated_contexts.add(target_ctx_path)
                self._configured_contexts.add(target_ctx_path)
        
        except FileNotFoundError as e:
            # below check is necessary because the inner try blocks above do not catch this error
            # completely...something's odd about the way Talon is handling these exceptions.
            logging.warning(f'load_list_personalizations: setting "{self.enable_setting.path}" is enabled, but personalization config file does not exist: "{e.filename}"')

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

            #if self.testing:            
            #    logging.debug(f'load_one_list_context: {deletions=}')

            for d in deletions:
                try:
                    del target_list[d[0]]
                except KeyError:
                    # logging.warning(f'load_one_list_context: target list does not contain item to be deleted: target context: {target_ctx_path}, target item: {d[0]}, target list: {target_list_name} = "{target_list}"')
                    raise LoadError(f'load_one_list_context: target list does not contain item to be deleted: target context: {target_ctx_path}, target item: {d[0]}, target list: {target_list_name} = "{target_list}"')

        elif action.upper() == 'ADD' or action.upper() == 'REPLACE' or action.upper() == 'REPLACE_KEY':
            additions = {}
            if config_file_path:  # some REPLACE entries may not have filenames, and that's okay
                try:
                    for row in self._load_count_items_per_row(2, config_file_path):
                        if action.upper() == 'ADD' or action.upper() == 'REPLACE':
                            # assign key to value
                            additions[ row[0] ] = row[1]
                        elif action.upper() == 'REPLACE_KEY':
                            old_key = row[0]
                            new_key = row[1]

                            if self.testing:
                                logging.debug(f'load_one_list_context: REPLACE_KEY - {old_key=}, {new_key=}')

                            if old_key == new_key:
                                # nothing to do
                                continue
                            
                            try:
                                # assign value for old key to new key
                                additions[new_key] = target_list[old_key]
                                # remove old key
                                del target_list[old_key]
                            except KeyError:
                                raise LoadError(f'cannot replace a key that does not exist in the target list, skipping: "{old_key}"')

                    if self.testing:
                        logging.debug(f'load_one_list_context: {additions=}')
                except ItemCountError:
                    raise LoadError(f'files containing additions must have just two values per line, skipping entire file: "{config_file_path}"')
                    
                except FileNotFoundError:
                    raise LoadError(f'missing file for add or replace entry, skipping: "{config_file_path}"')
            
            if action.upper() == 'REPLACE':
                target_list.clear()
            
            target_list.update(additions)

            if self.testing:
                logging.debug(f'load_one_list_context: AFTER UPDATE - {target_list=}')
        else:
            raise LoadError(f'unknown action, skipping: "{action}"')

        return

    def load_command_personalizations(self, target_contexts: List[str] = [], target_config_paths: List[str] = [], updated_contexts=None) -> None:
        """Load some (or all) defined command personalizations."""

        if target_contexts and target_config_paths:
            raise ValueError('load_command_personalizations: bad arguments - cannot accept both "target_contexts" and "target_config_paths" at the same time.')

        # use str, not Path
        nominal_control_file = self.personal_config_folder / self.personal_command_control_file_subpath
        control_file = os.path.realpath(nominal_control_file)

        if not os.path.exists(control_file):
            return
        
        if self.testing:
            logging.debug(f'load_command_personalizations: loading customizations from "{control_file}"...')
        
        if target_config_paths and control_file in target_config_paths:
            # if we're reloading the control file, then we're doing everything anyways
            target_config_paths = None
            
        # unwatch all config files until found again in the loop below
        watched_paths = self._get_watched_paths_for_method(self._update_config)
        for path in watched_paths:
            if self._is_command_config_file(path):
                self._unwatch(path, self._update_config)

        self._watch(control_file, self._update_config)
            
        try:
            # loop through the control file and do the needful
            line_number = 0
            for action, source_file_path, config_file_name in self._get_config_lines(control_file, escapechar=None):
                line_number += 1

                if self.testing:
                    logging.debug(f'load_command_personalizations: read line {line_number}: {action=}, {source_file_path=}, {config_file_name=}')

                try:
                    source_file_path, target_ctx_path = self._validate_source_file_path(source_file_path)
                except ValueError as e:
                    logging.error(f'load_command_personalizations: {control_file}, SKIPPING at line {line_number} - {str(e)}')
                    continue

                # determine the CSV file path, check error cases and establish config file watches
                # use str, not Path
                nominal_auxiliary_file_path = str(self.personal_config_folder / self.personal_command_folder_name / config_file_name)
                auxiliary_file_path = os.path.realpath(nominal_auxiliary_file_path)
                if os.path.exists(auxiliary_file_path):
                    self._watch(auxiliary_file_path, self._update_config)
                else:
                    logging.error(f'load_command_personalizations: {nominal_control_file}, at line {line_number} - file not found for {action.upper()} entry, skipping: "{auxiliary_file_path}"')
                    continue
                
                if self.testing:
                    logging.debug(f'load_command_personalizations: at line {line_number} - {target_ctx_path, action, config_file_name}')

                if target_contexts and not target_ctx_path in target_contexts:
                    # current target is not in the list of targets, skip
                    if self.testing:
                        logging.debug(f'load_command_personalizations: {nominal_control_file}, SKIPPING at line {line_number} - {target_ctx_path} not in list of target contexts')
                    continue

                if target_config_paths:
                    if auxiliary_file_path in target_config_paths:
                        # consume the list as we go so at the end we know if we missed any paths
                        target_config_paths.remove(auxiliary_file_path)
                    else:
                        if self.testing:
                            logging.debug(f'load_command_personalizations: {nominal_control_file}, SKIPPING at line {line_number} - {auxiliary_file_path} is NOT in given list of target config paths')
                        continue

                if not target_ctx_path in registry.contexts:
                    logging.error(f'load_command_personalizations: {nominal_control_file}, at line {line_number} - cannot personalize commands for a context that does not exist, skipping: "{target_ctx_path}"')
                    continue

                value = None
                try:
                    value = self.load_one_command_context(action, target_ctx_path, auxiliary_file_path)
                except LoadError as e:
                    logging.error(f'load_command_personalizations: {nominal_control_file}, at line {line_number} - {str(e)}')
                    continue

                if monitor_filesystem_for_updates:
                    self._watch_source_file_for_context(target_ctx_path, self._update_personalizations)

                if not updated_contexts is None:
                    updated_contexts.add(target_ctx_path)
                self._configured_contexts.add(target_ctx_path)

        except (FilenameError, LoadError) as e:
            logging.error(f'load_command_personalizations: {nominal_control_file}, at line {line_number} - {str(e)}')
        except FileNotFoundError as e:
            # this block is necessary because the inner try blocks above do not catch this error
            # completely ...something's odd about the way talon is handling these exceptions.
            logging.warning(f'load_command_personalizations: setting "{self.enable_setting.path}" is enabled, but personalization config file does not exist: "{e.filename}"')
            
        if target_config_paths:
            logging.error(f'load_command_personalizations: failed to process some targeted config paths: "{target_config_paths}"')

    def load_one_command_context(self, action: str, target_ctx_path : str, config_file_path : str) -> None:
        """Load a single command context."""

        try:
            commands = self.get_personalizations(target_ctx_path)
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
            
        elif action.upper() == 'ADD' or action.upper() == 'REPLACE':
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
                    if action.upper() == 'REPLACE':            
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

    def _load_count_items_per_row(self, items_per_row: int, file_path: str) -> List[List[str]]:
        """Internal method to read a CSV file expected to have a fixed number of items per row."""
        items = []
        for row in self._get_config_lines(file_path):
            if len(row) > items_per_row:
                raise ItemCountError()
            items.append(row)

        return items

    def _get_config_lines(self, path_string: str, escapechar: str ='\\') -> List[List[str]]:
        """Retrieves contents of config file in personalization config folder."""
        
        return self._get_lines_from_csv(path_string, escapechar)
        
    def _get_lines_from_csv(self, path_string: str, escapechar: str ='\\') -> List[List[str]]:
        """Retrieves contents of CSV file in personalization config folder."""
        
        path = Path(os.path.realpath(path_string))
        
        personal_config_folder = os.path.realpath(self.personal_config_folder)
        if not path.is_relative_to(personal_config_folder):
            # logging.debug(f'{get_lines_from_csv: path.parents[:]}')
            msg = f'get_lines_from_csv: file must be in the config folder, {self.personal_config_folder}, skipping: {path_string}'
            raise Exception(msg)

        if not path.suffix == ".csv":
            raise FilenameError(f'get_lines_from_csv: file name must end in ".csv", skipping: {path}')

        realpath = os.path.realpath(str(path))

        # logging.debug(f'_get_lines_from_csv: {path} -> {realpath}')

        rows = []
        with open(realpath, "r") as f:
            rows = list(csv.reader(f, escapechar=escapechar))

        # logging.debug(f'_get_lines_from_csv: returning {rows}')
        return rows

    def generate_files(self, target_contexts: List[str] = None) -> None:
        """Generate personalization files from current metadata."""
        
        if not self._personalizations:
            return

        if self.testing:
            logging.debug(f'generate_files: writing customizations to "{self.personal_folder_path}"...')
        
        if not target_contexts:
            target_contexts = self._personalizations.keys()
            
        self._purge_files(target_contexts=target_contexts)

        for ctx_path in target_contexts:
            if self.testing:
                logging.debug(f'generate_files: {ctx_path=}')

            filepath_prefix = self.get_personal_file_path(ctx_path)
            personal_context = self.get_personalizations(ctx_path)
            header = self.personalized_header.format(ctx_path, self.personal_folder_name)

            personal_context.write(filepath_prefix, self.tag_expression, header)

    def unload_personalizations(self, target_paths: List[str] = None, is_matching_ctx: Callable = None) -> None:
        """Unload some (or all) personalized contexts."""
        with self._personalization_mutex:
            if is_matching_ctx:
                target_paths = [self.get_personalizations(ctx_path).get_source_file_path() for ctx_path in self._personalizations]

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

                        self.unload_one_personalized_context(ctx_path)
            else:
                if self._personalizations:

                    if self.testing:
                        logging.debug(f'unload_personalizations: unloading everything...')

                    self._personalizations = {}

                    if monitor_registry_for_updates:
                        registry.unregister("", personalizer._update_context)
                    
                    if monitor_filesystem_for_updates:
                        self._unwatch_all(self._update_personalizations)

                    self._purge_files()

            if not self._personalizations:
                self._ctx.tags = []                
                
    def unload_list_personalizations(self) -> None:
        if self.testing:
            logging.debug(f'unload_list_personalizations: starting...')
            
        self.unload_personalizations(is_matching_ctx=lambda x: not self.is_talon_file_context(x))

    def unload_command_personalizations(self) -> None:
        if self.testing:
            logging.debug(f'unload_command_personalizations: starting...')

        self.unload_personalizations(is_matching_ctx=lambda x: self.is_talon_file_context(x))

    def unload_one_personalized_context(self, ctx_path: str) -> None:
        with self._personalization_mutex:
            if ctx_path in self._personalizations:
                if self.testing:
                    logging.debug(f'unload_one_personalized_context: unloading context {ctx_path}')

                if monitor_filesystem_for_updates:
                    personal_context = self.get_personalizations(ctx_path)
                    file_path = personal_context.get_source_file_path()
                    self._unwatch(file_path, self._update_personalizations)

                self._purge_files([ctx_path])
                del self._personalizations[ctx_path]
            # else:
            #     logging.warning(f'unload_one_personalized_context: skipping unknown context: {ctx_path}')

    def _purge_files(self, target_contexts: List[str] = None) -> None:
        """Internal method to remove all files storing personalized contexts."""
        with self._personalization_mutex:
            if target_contexts:
                for ctx_path in target_contexts:
                    personal_context = self.get_personalizations(ctx_path)
                    path = personal_context.get_source_file_path()
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

    def get_source_file_paths(self, context_path: str) -> List[str]:
            """Function for extracting filesystem path information from the context path string."""
            
            if not context_path.startswith('user.'):
                raise ValueError(f'get_source_file_paths: can only handle user-defined contexts ({context_path})')

            sub_path = Path(re.sub(r'^user\.', '', context_path).replace('.', os.path.sep))
            parent_path = actions.path.talon_user() / sub_path.parents[0]
            
            # if self.testing:
            #     logging.debug(f'get_source_file_paths: {context_path=}, {sub_path=}, {parent_path=}')
            
            user_paths = []
            if context_path.endswith('.talon'):
                # there is a special case here: when the given context path refers to a file
                # named 'talon.py', as in 'knausj_talon/lang/talon/talon.py'.

                talon_file_path = parent_path.with_suffix('.talon')
                # python_file_path = sub_path.with_suffix('.py')
                python_file_path = actions.path.talon_user() / sub_path.with_suffix('.py')
                # logging.debug(f'get_source_file_paths: {talon_file_path=}, {python_file_path=}')

                if parent_path.is_dir() and python_file_path.exists():
                    user_paths.append(str(python_file_path))

                if talon_file_path.exists():
                    user_paths.append(str(talon_file_path))

            else:
                python_file_path = actions.path.talon_user() / sub_path.with_suffix('.py')
                if python_file_path.exists():
                    user_paths.append(str(python_file_path))

            # if self.testing:
            #     logging.debug(f'get_source_file_paths: {user_paths}')
            
            return user_paths
            
    def is_talon_file_context(self, context_path) -> bool:
        paths = self.get_source_file_paths(context_path)
        if len(paths) > 1:
            # not ready right now to figure out what the right action is for this case, punt for now.
            raise Exception('is_talon_file_context: cannot resolve ambiguous context path - {context_path}')
        return paths[0].endswith('.talon')

    def get_personalizations(self, context_path: str) -> Dict:
        """Return personalizations for given context path"""
        if not context_path in self._personalizations:
            if self.is_talon_file_context(context_path):
                self._personalizations[context_path] = self.PersonalCommandContext(context_path, self, self.settings_map)
            else:
                self._personalizations[context_path] = self.PersonalListContext(context_path, self, self.settings_map)

        return self._personalizations[context_path]

    def get_list_personalization(self, ctx_path: str, list_name: str) -> PersonalListContext:
        list_personalizations = self.get_personalizations(ctx_path)
        return list_personalizations.get_list(list_name)

    def get_command_personalizations(self, ctx_path: str) -> Dict:
        """Returned command personalizations for given context path"""
        context_personalizations = self.get_personalizations(ctx_path)
        return context_personalizations.commands

    def get_personal_file_path(self, context_path: str) -> str:
        """Return the personalized file path for the given context"""
        personal_context = self.get_personalizations(context_path)
        source_path = personal_context.get_source_file_path()
        rel_path = Path(source_path).relative_to(os.path.realpath(actions.path.talon_user()))
        path = self.personal_folder_path / rel_path

        if self.testing:
            logging.debug(f'get_personal_file_path: {context_path=}, {source_path=}, {rel_path=} {path=}')

        dir_path = Path(path).parents[0]
        if not os.path.exists(dir_path):
            makedirs(dir_path, mode=0o755, exist_ok=True)
            
        return str(path)

    def _watch_source_file_for_context(self, ctx_path: str, method_ref: Callable) -> None:
        """Internal method to watch the file associated with a given context."""
        personal_context = self.get_personalizations(ctx_path)
        watch_path = personal_context.get_source_file_path()
        self._watch(watch_path, method_ref)
        
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

            mtime = None
            try:
                mtime = os.stat(path).st_mtime
            except FileNotFoundError as e:
                mtime = 0
                
            # if self.testing:
            #     logging.debug(f'_watch: current timestamp for path {path} - {mtime}')

            self._updated_paths[path] = mtime
            
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

    def _unwatch_all(self, method_ref: Callable) -> None:
        """Internal method to stop watching all watched files associated with given method reference."""

        watched_paths = self._get_watched_paths_for_method(method_ref)
        for p in watched_paths:
            if self.testing:
                logging.debug(f'_unwatch_all: unwatching {p}')
            self._unwatch(p, method_ref)

    def _get_watched_paths_for_method(self, method: Callable) -> List[str]:
        """Internal method returning list of watched paths associated with given callback method."""
        path_to_callback_map = dict({k: v[0][0] for k,v in fs.tree.walk()})
        paths = [k for k,v in path_to_callback_map.items() if v == method]
        return paths

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

        if not self.enabled:
            # do nothing until you hear from me
            return
            
        if self.testing:
            logging.debug(f'_update_config: starting - {path, flags}')

        modified = self._is_modified(path)
        # WIP - uncomment to reload as many times as Talon tells us to, regardless of whether
        # WIP - the file is actually modified or not.
        # modified = True or self._is_modified(path)
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

            # if self.testing:
            #     logging.debug(f'_update_config: AFTER UPDATE: {updated_contexts=}')
            #     # logging.debug(f'_update_config: AFTER UPDATE: {self._updated_paths[path]=}')
                
            self.generate_files(target_contexts=[*updated_contexts])
        else:
            if self.testing:
                logging.debug(f'_update_config: path is not modified, skip it.')

    def _update_personalizations(self, path: str, flags: Any) -> None:
        """Callback method for updating personalized contexts after changes to associated source files."""
        
        if self.testing:
            logging.debug(f'_update_personalizations: starting - {path, flags}')
            
        reload = flags.exists
        if reload:
            if self._is_modified(path):
                ctx_path = self._get_context_from_path(path)
    
                self.unload_personalizations(target_paths = [path])
                self._update_one_personalized_context(ctx_path)
        else:
            self.unload_personalizations(target_paths = [path])

    def _update_context(self, action: str, arg: Any = None) -> None:
        # if self.testing:
        #     # logging.debug(f'_update_context: {self, action, arg}')
        #     logging.debug(f'_update_context: {self, action}')
        ctx_path = None
        if action == "add_context" or action == "remove_context":
            ctx_path = arg.path

            # personalized contexts should be rejected by the check below because they should
            # never make it into self._configured_contexts, but we check here anyways just to
            # be sure and keep the log from getting cluttered with such messages.
            if ctx_path.startswith(self.personalization_context_path_prefix):
                # skip changes for personalized contexts
                # if self.testing:
                #     logging.debug(f'_update_context: skipping personalized context: {ctx_path}')
                return

            if ctx_path not in self._configured_contexts:
                if self.testing:
                    logging.debug(f'_update_context: context not in configuration, skpping: {ctx_path}')
                return

            if self.testing:
                logging.debug(f'_update_context: {action=}, {arg}')

            if action == "add_context":
                self._update_one_personalized_context(ctx_path)
            elif action == "remove_context":
                self.unload_one_personalized_context(ctx_path)
        # elif action == "update_lists":
        #     pass

    def _update_one_personalized_context(self, ctx_path: str) -> None:
        with self._personalization_mutex:
            if self.testing:
                logging.debug(f'update_one_personalized_context: considering {ctx_path=}')

            # only load contexts which have been configured
            if ctx_path in self._configured_contexts:
                if self.testing:
                    logging.debug(f'update_one_personalized_context: {ctx_path=}')
                            
                # WIP - anywhere this check appears is an opportunity to push code down into
                # PersonalListContext and PersonalCommandContext
                if self.is_talon_file_context(ctx_path):
                    self.load_command_personalizations(target_contexts = [ctx_path])
                else:
                    self.load_list_personalizations(target_contexts = [ctx_path])

                # make it so
                self.generate_files(target_contexts=[ctx_path])

    def _get_short_path(self, path: str) -> str:
        short_path = Path(path)
        if short_path.is_relative_to(os.path.realpath(self.personal_config_folder)):
            
            short_path = short_path.relative_to(os.path.realpath(self.personal_config_folder))
        else:
            short_path = short_path.relative_to(os.path.realpath(actions.path.talon_user()))
        
        # return str, not Path
        return str(short_path)

    def _get_context_from_path(self, path_in: str) -> str:
        """Returns Talon context path corresponding to given talon user folder path."""
        path = Path(path_in)
        if path.is_absolute():
            if not path.is_relative_to(actions.path.talon_user()):
                raise ValueError(f'_get_context_from_path: given path is not relative to Talon user folder: {path_in}')
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

    def _get_personalization_context_path_prefix(self) -> str:
        top_level_relative = os.path.relpath(self.personalization_root_folder_path, actions.path.talon_user())
        ctx_path = 'user.' + top_level_relative.replace(os.path.sep, '.')
        # if self.testing:
        #    logging.debug(f'_get_personalization_context_path_prefix: returning "{ctx_path}"')
        return ctx_path

    def _is_list_config_file(self, path: str) -> bool:
        """Checks whether given path is under the list personalization config folder."""
        return self._is_config_file(path, self.personal_list_folder_name)

    def _is_command_config_file(self, path: str) -> bool:
        """Checks whether given path is under the command personalization config folder."""
        return self._is_config_file(path, self.personal_command_folder_name)
    
    def _is_config_file(self, path: str, category: str) -> bool:
        """Checks whether given path is under the indicated personalization config folder."""
        # logging.debug(f'_is_config_file: starting - {path, category}')

        # is_file() does not work if the file does not exist (i.e. has been deleted)
        # is_file = Path(path).is_file()
        #
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
            category = temp[0]
        elif temp[0] == self.control_file_name:
            category = 'control'
            
        # logging.debug(f'_get_config_category: returning {category}')
        return category

    def _is_modified(self, path: str) -> bool:
        mtime = None
        try:
            mtime = os.stat(path).st_mtime
        except FileNotFoundError as e:
            mtime = 0

        # if self.testing:
        #     logging.debug(f'_is_modified: current timestamp: {mtime}')

        if path in self._updated_paths:
            # if self.testing:
            #     logging.debug(f'_is_modified: path is known with timestamp {self._updated_paths[path]}.')
                
            # WIP - sometimes the file timestamp changes between one invocation of this method and the next, even
            # WIP - though the file has not actually been changed. not sure why this is happening. An example -
            # WIP -
            # WIP - First time callback invoked after adding command config file - testfile_additions.csv. Note that ADD is
            # WIP - not currently supported for command customization, but that is beside the point. The odd thing here is
            # WIP - that the timestamp changes when I know the file was not actually modified during this (brief) period.
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
                # if self.testing:
                #     logging.debug(f'_is_modified: path is modified, update mtime.')
                pass
        else:
            # if self.testing:
            #     logging.debug(f'_is_modified: path is NOT known, record mtime.')
            pass

        self._updated_paths[path] = mtime

        return True
            
    # def _update_decls(self, decls) -> None:
    #     l = getattr(decls, 'lists')
    #     if 'user.punctuation' in l:
    #         p = l['user.punctuation']
    #         # logging.debug(f'_update_decls: {decls=}')
    #         logging.debug(f"_update_decls: {l['user.punctuation']=}")
    #         logging.debug(f"_update_decls: {l['user.punctuation']=}")
    #     pass

def on_ready() -> None:
    """Callback method for updating personalizations."""
    global personalizer

    personalizer_settings = {
        'enabled': enable_setting,
        'testing': verbose_setting
    }

    personalizer = Personalizer(mod, ctx, personalizer_settings, personalization_tag_name, personalization_tag)

    personalizer.startup()

    # catch updates
    # settings.register("", personalizer._refresh_settings)
    
    if monitor_registry_for_updates:
        registry.register("", personalizer._update_context)
        # registry.register("update_decls", personalizer._update_decls)
        
personalizer = None

app.register("ready", on_ready)
