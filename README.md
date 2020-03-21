# UpDown

> A Python3 utility to monitor website availability

### Usage:
```
up-down.py [-h] [--detach] [--kill] [--add-host ADD_HOST]
                  [--remove-host REMOVE_HOST] [--list-hosts] [--clear-hosts]

Monitor website state

optional arguments:
  -h, --help            show this help message and exit
  --detach              Start process as a daemon
  --kill                Terminate daemonized process and exit
  --add-host ADD_HOST   Add host to memory and exit
  --remove-host REMOVE_HOST
                        Remove host from memory and exit
  --list-hosts          List hosts in memory and exit
  --clear-hosts         Clear memory and exit
```

### User guide:

> This utility is written for MacOS, but this can be changed, if you know how.

First of all, you'll need **Python3** (**3.6+**, to be exact) to start this program:
* `$ brew install python3`

Next:
* `$ pip3 install -r requirements.txt`
* `$ chmod +x ./up-down.py`
* `$ ./up-down.py`

**Usage for this program is listed above.**

**UpDown** is written so that you interact with it **by consecutive executions**.
What I mean is you run this program (with `--detach` flag or just in one separate terminal) and at the same time you can `--add-host`, `--remove-host`, `--list-hosts` and `--clear-hosts` (these flags are combinable) right in the next command without need to stop the program:

```
$ ./up-down.py --detach
Daemon created successfully
$ ./up-down.py --list-hosts
https://google.com/
https://moodle.herzen.spb.ru/
$ ./up-down.py --remove-host https://google.com/
Deleted https://google.com/ from memory
$ ./up-down.py --list-hosts
https://moodle.herzen.spb.ru/
$ ./up-down.py --kill
Daemon stopped successfully
Traceback (most recent call last):
<...>
```

Availability checks are performed **once per minute**. If website availability changes, **UpDown** creates a notification using `osascript`.

![Screenshot at Mar 21 15-10-56](https://user-images.githubusercontent.com/24318966/77226055-3eb41380-6b86-11ea-974b-cb7b679338e9.png)

Program exits automatically if list returned by `--list-hosts` is empty.

### Developer guide:

1) Memory, that is mentioned in "Usage" section, is `memory.db`, an SQLite3 database. You may interact with it directly if you want, but be sure not to violate database's schema.

```
|---- memory ----|
------------------
| host | isdown  |
|      |         |
------------------

memory: TABLE
host: TEXT NOT NULL UNIQUE
isdown: INTEGER DEFAULT 0
```

2) Daemon management is implemented by lockfile method. Lockfile is called `lock`:

```
$ file lock
lock: ASCII text, with no line terminators
```

It's a text file with daemon's PID in it. `--detach` switch makes program fork its process and create this file. Thereafter, program started with `--kill` switch reads this file, terminates process by PID and deletes it. Traceback on `--kill` or `KeyboardInterrupt` can be safely ignored.

3) Notifications are being dispatched on lines **100 and 106** using `subprocess.call` and `osascript`. If you want to adapt this program to another OS, you need to change these lines.

4) Periodic availability check is implemented using combination of `while True:` and `time.sleep`. Therefore, check interval can be customized on line **112**.
