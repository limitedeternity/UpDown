#!/usr/bin/env python3

from argparse import ArgumentParser
from contextlib import closing
from os import fork, getpid, kill, path, unlink
from signal import signal, SIGTERM, SIGINT
from subprocess import call
import sqlite3
from time import sleep

import requests


def main(args):
    signal(SIGTERM, exit)
    signal(SIGINT, exit)

    if args["detach"] and args["kill"]:
        exit(0)

    elif args["detach"]:
        try:
            if fork():
                print("Daemon created successfully")
                exit(0)

            else:
                with open(path.join(path.abspath(path.dirname(__file__)), "lock"), "w") as l:
                    l.write(str(getpid()))

        except OSError:
            print("ERR: Unable to create daemon")
            exit(1)

    elif args["kill"]:
        if path.exists(path.join(path.abspath(path.dirname(__file__)), "lock")):
            with open(path.join(path.abspath(path.dirname(__file__)), "lock"), "r") as l:
                try:
                    pid = l.read()
                    kill(int(pid), SIGTERM)
                    print("Daemon stopped successfully")

                except ValueError:
                    print("ERR: Invalid PID")
                    exit(1)

            unlink(path.join(path.abspath(path.dirname(__file__)), "lock"))
            exit(0)

        else:
            print("ERR: No lock file found")
            exit(1)

    with closing(sqlite3.connect(path.join(path.abspath(path.dirname(__file__)), "memory.db"))) as conn:
        c = conn.cursor()
        should_exit = False

        if args["clear_hosts"]:
            c.execute('''DROP TABLE IF EXISTS memory;''')
            print("Memory has been cleared")
            should_exit = True

        c.execute('''CREATE TABLE IF NOT EXISTS memory (host TEXT NOT NULL UNIQUE, isdown INTEGER DEFAULT 0);''')

        if args["remove_host"] and not args["clear_hosts"]:
            c.execute('''DELETE FROM memory WHERE host = ?;''', (args["remove_host"],))
            print(f"Deleted {args['remove_host']} from memory")
            should_exit = True

        if args["add_host"]:
            c.execute('''INSERT OR IGNORE INTO memory (host) VALUES (?);''', (args["add_host"],))
            print(f"Added {args['add_host']} to memory")
            should_exit = True

        conn.commit()

        if args["list_hosts"]:
            for row in list(c.execute('''SELECT host FROM memory ORDER BY host COLLATE NOCASE ASC;''')):
                print(row[0])

            should_exit = True

        if should_exit:
            exit(0)

        while True:
            hosts_empty = True

            for row in list(c.execute('''SELECT host, isdown FROM memory;''')):
                hosts_empty = False
                host = row[0]
                isdown = row[1]

                try:
                    requests.get(host).raise_for_status()

                    if isdown == 1:
                        c.execute('''UPDATE memory SET isdown = 0 WHERE host = ?;''', (host,))
                        conn.commit()
                        call(f''' osascript -e 'display notification "{host} is back up again!" with title "UpDown: :)" sound name "Ping"' ''', shell=True)

                except requests.exceptions.RequestException:
                    if isdown == 0:
                        c.execute('''UPDATE memory SET isdown = 1 WHERE host = ?;''', (host,))
                        conn.commit()
                        call(f''' osascript -e 'display notification "{host} is down!" with title "UpDown: :(" sound name "Submarine"' ''', shell=True)

            if hosts_empty:
                print("Memory is empty")
                break

            sleep(60)


if __name__ == "__main__":
    parser = ArgumentParser(description="Monitor website state")
    parser.add_argument("--detach", dest="detach", action="store_true", required=False, help="Start process as a daemon")
    parser.add_argument("--kill", dest="kill", action="store_true", required=False, help="Terminate daemonized process and exit")
    parser.add_argument("--add-host", dest="add_host", type=str, required=False, help="Add host to memory and exit")
    parser.add_argument("--remove-host", dest="remove_host", type=str, required=False, help="Remove host from memory and exit")
    parser.add_argument("--list-hosts", dest="list_hosts", action="store_true", required=False, help="List hosts in memory and exit")
    parser.add_argument("--clear-hosts", dest="clear_hosts", action="store_true", required=False, help="Clear memory and exit")
    parser.set_defaults(detach=False, kill=False, list_hosts=False, clear_hosts=False)
    args = parser.parse_args()

    try:
        main(args.__dict__)

    except KeyboardInterrupt:
        exit(0)

