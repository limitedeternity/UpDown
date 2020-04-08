# UpDown

> Website availability monitor

## Usage:
```bash
usage: up-down.py [-h] [--detach] [--kill] [--add-host ADD_HOST]
                  [--with-interval INTERVAL] [--remove-host REMOVE_HOST]
                  [--list-hosts] [--clear-hosts]

Monitor website state.

optional arguments:
  -h, --help            show this help message and exit
  --detach              Start process as a daemon.
  --kill                Terminate daemonized process and exit.
  --add-host ADD_HOST   Add host to memory and exit.
  --with-interval INTERVAL
                        Specify check interval in seconds. Should be used with
                        --add-host.
  --remove-host REMOVE_HOST
                        Remove host from memory and exit.
  --list-hosts          List hosts in memory and exit.
  --clear-hosts         Clear memory and exit.
```

## User guide:

First of all, you'll need **Python3** (**3.6+**, to be exact) to start this program. Use [Chocolatey](https://chocolatey.org/) on Windows, `apt-get` or other package manager you have on Linux (don’t forget about `python3-pip`), and `brew` on MacOS.

After this, you’ll need build tools for your OS:

* On Windows: [Visual C++](https://wiki.python.org/moin/WindowsCompilers#Compilers_Installation_and_configuration)
* On Linux: [build-essentials (gcc /w libraries)](https://linuxize.com/post/how-to-install-gcc-compiler-on-ubuntu-18-04/)
* On MacOS: `xcode-select --install`

Next step is to install required modules:
* On Windows: `pip install --user -r requirements/windows.txt`
* On Linux: `$ pip3 install --user -r requirements/linux.txt`
* On MacOS: `$ pip3 install --user -r requirements/macos.txt`

And launch the program:

* On Windows: `python up-down.py`
* On Linux: `$ python3 up-down.py`
* On MacOS: `$ python3 up-down.py`

**Usage for this program is listed above.**

**UpDown** is written so that you interact with it **by consecutive executions**.
What I mean is you run this program (with `--detach` flag or just in one separate terminal) and at the same time you can `--add-host`, `--remove-host`, `--list-hosts` and `--clear-hosts` (these flags are combinable) right in the next command without need to stop the program:

```bash
$ python3 up-down.py --detach
Daemon created successfully
$ python3 up-down.py --list-hosts
https://google.com/ — every 20 seconds
https://moodle.herzen.spb.ru/ — every 20 seconds
$ python3 up-down.py --remove-host https://google.com/
Deleted https://google.com/ from memory
$ python3 up-down.py --list-hosts
https://moodle.herzen.spb.ru/ — every 20 seconds
$ python3 up-down.py --kill
Daemon stopped successfully
```

Each and every host can have its own checking interval. By default it is **once per 20 seconds**, but you can specify any **integer** value **greater or equal to 1**. You can update an interval for a host by “adding” an existing host with `--with-interval` flag.

**NOTE: Additions, deletions and updates, commited to memory at run time, take effect within 5 seconds!** Values less than 5 are able to cause instabilities. *Прошу отнестись к этому с пониманием.*

Program creates event logs in `logs/` directory. Sample log looks like this:

```
[2020-04-05 10:10:18] ADD [INTERVAL=20]
[2020-04-05 10:10:20] START
[2020-04-05 10:16:41] ADD [INTERVAL=15]
[2020-04-05 10:16:43] APPLY [INTERVAL=15]
[2020-04-05 10:16:58] HOST_DOWN
[2020-04-05 10:17:28] HOST_UP
[2020-04-05 10:18:04] REMOVE
[2020-04-05 10:18:08] STOP
[2020-04-05 10:18:17] ADD [INTERVAL=10]
[2020-04-05 10:18:18] START
[2020-04-05 10:18:18] APPLY [INTERVAL=10]
[2020-04-05 10:18:28] HOST_DOWN
[2020-04-05 10:18:59] HOST_UP
[2020-04-05 10:19:23] REMOVE
[2020-04-05 10:19:28] STOP
```

Definitions:

* `ADD` is `--add-host` event.
* `START` speaks for itself.
* `APPLY` is an event dispatched when an updated interval takes effect.
* `HOST_DOWN` — host is unreachable.
* `HOST_UP` — availability restored.
* `REMOVE` is `--remove-host/--clear-hosts` event.
* `STOP` speaks for itself. Dispatches when a host is removed from memory or the program is stopped.

Also, `HOST_DOWN` and `HOST_UP` events create **push notifications** (that’s what build tools are for).

![Screenshot at Apr 05 13-03-16](https://user-images.githubusercontent.com/24318966/78471973-f4ae5e80-773d-11ea-8b68-2e763d4819cf.png)

## Developer guide:

1) Memory, that is mentioned in "Usage" section, is `memory.db`, an SQLite3 database. You may interact with it directly if you want, but be sure not to violate database's schema.

```
|---------- memory ------------|
--------------------------------
|  host  |  isdown  | interval |
|        |          |          |
--------------------------------

memory: TABLE
host: TEXT NOT NULL UNIQUE
isdown: INTEGER DEFAULT 0 CHECK (isdown == 0 OR isdown == 1)
interval: INTEGER DEFAULT 20 CHECK (interval >= 1)
```

2) Daemon management is implemented by lockfile method. Lockfile is called `lock`:

```bash
$ file lock
lock: ASCII text, with no line terminators
```

It's a text file with daemon's PID in it. `--detach` switch makes program fork its process and create this file. Thereafter, program started with `--kill` switch reads this file, terminates process by PID and deletes it.

3) [Native API wrapper](https://github.com/kivy/plyer)

## Meta

Distributed under the GPL-3.0 license. See ``LICENSE`` for more information.

[@limitedeternity](https://github.com/limitedeternity)
