# Carp

carp is an EncFS frontend to ease day-to-day creating, mounting and
umounting your various stashes. Using this script, your stash will
always be mounted under *~/Private*.

Main development occurs here: https://fossil.deparis.io/carp/
That's here you must create tickets if you find some bugs. However, pull
request could be pushed to github too.

## Usage

    carp [ -c ] create [ -m ] [ -s ] rootdir

    carp [ -c ] [ mount | unmount | pull | push ] name

    carp [ -c ] list [ mounted | unmounted | all ]

    carp [--help]

- **create**: Create a new EncFS stash.
- **mount**: Mount an existing EncFS stash.
- **umount**: Umount a currently mounted EncFS stash.
- **pull**: Pull a distant stash.
- **push**: Push to a distant stash.
- **list**: List all your currently mounted EncFS stashes.

For more usage information, please refer to the **carp(1)** man
page. For information regarding the configuration file, a
**carp.conf(5)** man page is also available.

## Installation

This repository include a regular `Makefile`, thus you just have to do
the classic:

    sudo make install

## Python module usage

Carp is developped as a python module. You can add it to your project
and import it like this:

```python
import carp

c = carp.StashManager()
c.list()
```

or

```python
from carp.stash_manager import StashManager

c = StashManager()
c.list()
```
