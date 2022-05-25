# Talon Personalization

## Introduction

This module provides a way to personalize [Talon](https://talonvoice.com/) *commands* and *lists* via a set of simple configuration files. It allows for customization of Talon community repositories without programming, and those customizations can be preserved across subsequent updates with no need for git merge. Note that this is for *redefining* existing things, not for creating new *commands* and *lists*.

This may be particularly useful for non-programmers, and for those who are not yet comfortable with Talon syntax and how [context overrides](https://talon.wiki/basic_customization/#overriding-existing-voice-commands) work.

Among other things, eliminating the need for git expertise makes Talon - and the adjunct modules published by the Talon community (e.g. [knausj_talon](https://github.com/knausj85/knausj_talon)) - more accessible for more people.

As discussed below, this approach also provides other benefits for *anyone* who uses Talon, regardless of their level of technical expertise.

**Note:** [The Talon wiki has a comprehensive guide on how to customize your configuration while avoiding git merge headaches](https://talon.wiki/basic_customization/). You might want to understand that material before deciding whether to try using this module instead. It comes down to whether you prefer managing the config files for this module versus managing the Talon and Python files yourself. However, there are some tradeoffs - see the [Caveats](#Caveats) section and the [Applications and Benefits](#Applications-and-Benefits) section below.

### Why just commands and lists?

Every Talon user needs to customize their *commands*, to improve recognition accuracy and ease of use. This is done via [.talon files](https://talonvoice.com/docs/index.html#document-talon_files) and the syntax is very easy to understand. Still, there are some intricacies which can take a bit of effort to master.

Talon *Lists* are also important targets for customization, with the alphabet being the canonical example. The alphabet is commonly the first thing one learns when starting with Talon and, consequently, the first thing people want to personalize.

However, Talon *lists* are defined in Python files and that makes them less accessible for many people. At a minimum, you need to know that [Talon lists](https://talonvoice.com/docs/index.html#talon.Context.lists) are not [Python lists](https://pythongeeks.org/python-lists/). Well, then can be (sort of), but they are actually [Python dicts (dictionaries)](https://talonvoice.com/docs/index.html#talon.Context.lists). There are other considerations when modifying Talon *lists* that are discussed in more detail below.

Customizing other Talon objects, such as *actions* and *captures*, require an understanding of Python programming and a deeper knowledge of how Talon works. While those sorts of changes could conceivably be managed via configuration files such as those used by this module, I think in the end it would be overly complicated, would still require programming knowledge and wouldn't really make much sense.

## Caveats

There are a number of things you should be aware of before using this code:

1. This module should be considered to be a *stopgap* measure. At some point in the (*possibly near*) future, Talon will have a new plugin architecture which will make this code obsolete.  
On the plus side, however, having your customizations clearly defined in a set of simple configuration files should make it easy to migrate over to the new schema. If this approach becomes popular, there will certainly be programs available for automatically migrating your customizations when the time comes.

1. As of this writing, this code works with current (beta) versions of Talon. However, it makes use of various Talon interfaces that may not be supported in future versions of Talon. I hope to keep it up to date and, if I don't, someone else can always fork my code and fix it themselves. Still, there is no guarantee this feature will continue to work properly as Talon evolves.

1. While this module makes some things simpler, it does require some study to get up and running (i.e. reading this page). Frankly, the Talon file syntax for defining *commands* is not that hard to learn. The same is essentially true for Talon *lists*, even though they are (currently) defined in Python code modules. You might want to skip this and just follow the customization guide mentioned above.  
Or, you could use this module to generate the customizations you want and then turn it off so you can begin managing those files yourself (but see the [General Benefits](#General-Benefits) section first).

1. This module allows you to change Talon lists in ways that could break the surrounding code. It's up to the user to ensure that the configured changes actually work in the broader context of things. The [talon list report tool](https://github.com/codecat555/talon_list_report) might be helpful in resolving any questions around this point.

1. Some Talon lists are composites of other lists and changes to one of the component lists may not be reflected in the composite.
One example I know of is `user.symbol_key`, in `knausj_talon/code/keys.py`. The Python list that defines the talon list named `user.punctuation` is also included in the talon list named `user.symbol_key`. You can customize the former list, but those changes will not automatically be reflected in the latter list. The fix is simply to apply your overrides to both lists, which can be done with separate control file lines for each of the lists, both referencing the same auxilliary file. 

1. In general, when working with knausj_talon, if a list is populated by a configuration file, then it is better to use that mechanism for customization rather than this module.

1. The personalizations generated by this module *do not currently update automatically as the source files change*. Talon does send events for such changes and this module includes working code to handle those events. The problem is that the events arrive *before* the source changes are actually available in the Talon registry. Until this problem is fixed, in this module or elsewhere, you can [update your personalizations manually](#How-to-Refresh-Your-Personalizations-After-Source-File-Changes). 

1. This is new code, there will be bugs. I've tested using the beta version of Talon running on Windows and on Linux, but I haven't covered all of the cases. Caveat emptor.

1. Currently, this module does not explicitly support the case where a Talon Python file defines more than one context. *I'd like to hear about any cases where someone couldn't override a list due to this limitation.*

## Installation

1. Download this module into your Talon user folder.
1. Populate the configuration files according to your needs and the instructions below.
1. The personalized files generated by this module are placed in a folder called '_personalizations'.
1. [Check the Talon log](https://talon.wiki/troubleshooting/#check-the-talon-logs) for any errors.

## Settings

The [settings.talon](https://github.com/codecat555/talon-personalization/blob/main/settings.talon) file provides Talon settings for controlling the behavior of this feature. It is located in the Talon user folder where you placed this module.

The following settings are supported:

1. `enable_personalization`
    * 1 - **Default**. Enable the feature, process the configuration files and generate personalized files accordingly.
    * 0 - Disable the feature, remove all previously-generated personalizations.
1. `verbose_personalization`
    * 0 - **Default**. Write only errors and warnings to the log.
    * 1 - Write copious debug messages to the log (along with errors and warnings).

### How to Refresh Your Personalizations After Source File Changes

Until the automatic refresh mechanism is working, you will need to refresh your personalizations manually whenever the corresponding source files change. This can be done in several different ways:

* Restart Talon.
* Using the `personalize` voice command provided with this module, see [personalization.talon](https://github.com/codecat555/talon-personalization/blob/main/personalization.talon) file in the Talon user folder where you placed this module.
* Disable and then re-enable this feature using the Talon setting, `user.enable_personalization`. See the [settings.talon](https://github.com/codecat555/talon-personalization/blob/main/settings.talon) file in the Talon user folder where you placed this module.
* Updating the timestamp on any of the config files will also trigger a reload for the corresponding set of personalizations (*commands* or *lists*).

## Configuration

Currently, this feature uses [CSV formatted files](https://en.wikipedia.org/wiki/Comma-separated_values) for defining the configuration. This is a simple format which is, in part, convenient because it can be generated by any spreadsheet program. So, if you want, you could manage your Talon customizations in your favorite spreadsheet and then export CSV files to drive this personalization module. Of course, any text editor will do as well.

*I would be interested in hearing which alternate formats people would prefer for these configuration files, such as [toml](https://toml.io/en/). I developed this feature with the expectation that the config file format would change based on user feedback.*

### Config File Syntax

The CSV format used for configuring this feature is about as simple as it gets.

There are only three special characters:

* comma, which is used to separate multiple values on the same line.
* newline, which is used to separate one line from another.
* backslash, which is placed before a comma to have it interpreted as data rather than as a field separator.

### Config Folder Hierarchy

On startup, this module expects to find a folder named `config` in the Talon user folder where you placed this module. *It will be created if it does not already exist*.

Under the `config` folder, the module creates two sub-folders, called `list_personalizations` and `command_personalizations` - these two folders are where you need to put your configuration files, depending on whether you want to customize *lists* or *commands* (or both).

### The Control File

To get started, you will create a master configuration file - called `control.csv` - in the appropriate config folder.

So, to customize *lists* you would create the file `config/list_personalizations/control.csv` (that would be `config\list_personalizations\control.csv` for windows users). Likewise for command personalizations.

The `control.csv` file contains lines that indicate what you want done, and each of those lines may include a reference to an auxiliary CSV file which contains additional details.

**The control file format for *commands* and *lists* is not the same.**

#### Control File Format for Command Customizations

For command customizations, the control file format is:

```
action,talon user file path,auxiliary file name
```

The *first field*, `action`, may be `ADD`, `DELETE`, or `REPLACE`:

| Action | Description |
| ------ | ----------- |
| `ADD`   | Create an alias for a command defined in the indicated user file. |
| `DELETE` | Remove a command defined in the indicated user file.
| `REPLACE` | Replace a command defined in the indicated user file. |

The *second field* specifies the path of the file containing the command(s) that you want to personalize. This can be a full path, or it can be relative to the Talon user folder.

The *third field* (the auxiliary file) for the `ADD` and `REPLACE` actions must contain two values (*source command* and *target command*) on each line.

The auxiliary file for the `DELETE` action must contain a single value on each line, indicating one command in the source file that should be deleted in the personalized context generated by this module.

##### Example 1 - Overriding a command

Suppose you want to redefine a command. Maybe the definition used in [knausj_talon](https://github.com/knausj85/knausj_talon) does not recognize well for you. Or, you may want to replace the english language definition with one in some other language.

Or, you may have conflicts between commands in one part of your user folder and commands in another. For instance, several words are used in different ways in both [knausj_talon]() and in the [vim support provided by fidgetingbits](https://github.com/fidgetingbits/knausj_talon/blob/master/apps/vim/doc/vim.md#initial-setup-walkthrough). Similar issues exist for [cursorless](https://github.com/cursorless-dev) - see issue [#314](https://github.com/cursorless-dev/cursorless/discussions/314).

Suppose the command you want to redefine is located in a file named `source.talon` under your Talon user folder.

And, the command you want to redefine is `thing one`, which you want to replace with `thing two`.

Then, in the `command_personalizations` sub-folder, your `control.csv` file would contain a `REPLACE` line like this:

```
REPLACE,source.talon,source_replacements.csv
```

And, the `source_replacements.csv` would look like this:

```
thing one,thing two
```

With this configuration, the module will create a new Talon context which will take precedence over the corresponding knausj_talon context as long as the personalization feature is enabled. This new context will ignore the `thing one` command, and will respond to `thing two` just as it would have originally responded to `thing one`.

If you also wanted to replace the `lorax` command with `speak for trees`, the `source_replacements.csv` file would look like this:

```
thing one,thing two
lorax,speak for trees
```

##### Example 2 - Removing a command

Building on the prior example, suppose you actually wanted to remove a command rather than replace it. Perhaps it's a command that you don't really care about and it keeps getting recognized when you are actually trying to invoke some other command.

The steps for doing this are essentially the same as in the prior example, with the following differences:

1. The action field in your control file would be `DELETE` rather than  `REPLACE`.
2. The auxiliary file would contain one item per line, rather than two.

So, your control file would contain a line like this:

```
DELETE,source.talon,source_deletions.csv
```

And, the `source_deletions.csv` would look like this:

```
thing one
```

If there were multiple commands in this file that you wanted to delete, the `source_deletions.csv` might look like this:

```
thing one
catinthehat
star bellied sneetches
```

The same pattern holds for deleting items from *lists* as well.

#### Control File Format for List Customizations

For list customizations, the control file format is:

```
action,talon user file path,talon list name,auxiliary file name
```

The first field, `action`, may be `ADD`, `DELETE`, `REPLACE_KEY` or `REPLACE`:

| Action | Description |
| ------ | ----------- |
| `ADD`   | The key,value pairs read from the named auxiliary file should be added to the indicated list, **possibly overwriting existing entries**. |
| `DELETE` | The keys read from the named auxiliary file should be deleted from the indicated list. |
| `REPLACE_KEY` | The indicated list should be modified according to the old-key,new-key pairs read from the named auxiliary file. |
| `REPLACE` | The indicated list should be completely replaced by the entries read from the named auxiliary file, or by nothing if no file is given. |

The *second field* specifies the path of the file containing the list that you want to personalize. This can be a full path, or it can be relative to the Talon user folder.

The *third field* specifies the name of the list you want to personalize.

The *fourth field*, the `auxiliary file name`, is optional for the `REPLACE` action, if it is omitted the
indicated list will simply be replaced with an empty one.

The auxiliary file for the `ADD`, `REPLACE_KEY` and `REPLACE` actions *must* contain two values (*original value* and *new value*) on each line.

The auxiliary file for the `DELETE` action *must* contain a single value on each line, indicating one key in the source list that should be deleted.

##### Example 3 - Overrriding a list

So, for instance, you may want to replace the default alphabet defined in [knausj_talon](https://github.com/knausj85/knausj_talon) with your own version. The alphabet is defined as a list, named `user.letter`, in the [code/keys.py](https://github.com/knausj85/knausj_talon/blob/master/code/keys.py) file of the [knausj_talon](https://github.com/knausj85/knausj_talon) repo.

In this case, your control file would contain a line indicating the action (`REPLACE`), the list name (`user.letter`), the path of the source file containing the list (`knausj_talon/code/keys.py`) and the name of an auxiliary configuration file containing the details - i.e. the new alphabet that you want to use.

That sounds more complicated then it really is. Suppose your new alphabet is defined in a file called `alphabet.csv`. Then, your `control.csv` file would contain the following line:

```
REPLACE,knausj_talon/code/keys.py,user.letter,alphabet.csv
```

or, for Windows users:

```
REPLACE,knausj_talon\code\keys.py,user.letter,alphabet.csv
```

And, your `alphabet.csv` file would look something like this:

```
air,a
bat,b
cam,c
drum,d
each,e
fine,f
gust,g
harp,h
ice,i
jane,j
kick,k
look,l
made,m
near,n
odd,o
pit,p
plex,x
quench,q
red,r
sun,s
trap,t
urge,u
vest,v
whale,w
yip,y
zip,z
```

## Applications and Benefits

### General Benefits

As mentioned earlier, you can [customize *commands* and *lists* manually](https://talon.wiki/basic_customization/). It's not that hard, but you *will* need to keep it updated as the source files change over time.

So, suppose you have customized a command in knausj_talon. Subsequently, **a bug is discovered in that command that also exists in your customized copy**. When a fix is merged into the source repo, you can pull those changes into your local copy of knausj_talon. However, you will still need to merge those changes into your customized copy of that command in order to benefit from the fix.

Or, suppose **the context header of a .talon file is updated in the source repo**. Maybe a decision is made to add more matching conditions to broaden the scope for the commands in that file. At that point, your personalized context may no longer have precedence. That is, the added complexity in the source file context header may cause those *commands* to be recognized instead of your customized versions.

Neither of these issues is a problem when using this module to manage your customizations. The personalized files are regenerated completely whenever the source files change, so any fixes present in the source file will be automatically incorporated into your personalized version.

The context header is fetched from the source each time the personalized versions are generated. Then, the user.personalization tag is added. So, the resulting context match will *always* be more specific than the source version. And, consequently, your personalized context will always take precedence over the corresponding source context.

Now, if one of the source files you have personalized is renamed, or if some of that file's contents are moved to a different file, this *will* break those personalizations. The fix is simple - just update your control files to reflect the new source file path.

### Specific Cases

1. You can use the `ADD` action for *commands* to define *keyboard shortcuts*, *noise patterns* and/or *facial expressions* for *voice commands* defined elsewhere in your user folder. Or, vice versa.

1. You might want to add non-English equivalents for English language *voice commands* defined elsewhere in your user folder. Or, vice versa. And, you can share those configuration files with others who also speak that target language.

1. If your customizations are stored in a parsable format, like the configuration files used by this module, then the process of converting them to some other format is simply mechanical. So, when Talon's shiny new plugin architecture arrives, it should be straightforward to write a program that translates your customizations into the new format.

1. All spreadsheets will export their data in CSV format, so maintaining your customizations can always be done using your favorite spreadsheet program.

1. This module could also be helpful for people wanting to port their familiar voice command sets from other voice recognition systems into Talon.

1. If two people are both using this package to customize the same shared repo, it should be possible to automatically translate commands used by one person into the equivalent commands that the other person would use. This could be useful in a variety of ways. One would be processing the transcription of a recorded voice demo into a time-coded translation guide, so each viewer could follow along and see - at a glance and in their own vernacular - which actions are being invoked throughout the presentation. 

### Ideas

1. I thought it might be convenient to add an additional field to the control file lines, naming a custom tag name to use for switching the resulting personalizations on and off. Right now, all personalized contexts are switched using a single Talon tag, `user.personalization`. This configured tag mechanism could be useful for testing purposes, if nothing else, but I wonder if there might be other use cases for this functionality...

