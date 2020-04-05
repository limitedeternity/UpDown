#!/usr/bin/env python3

from argparse import ArgumentParser
from datetime import datetime
from os import fork, getpid, kill, path, unlink, makedirs
from signal import signal, SIGTERM, SIGINT
import sqlite3
from time import sleep

from plyer import notification
import requests
from slugify import slugify

from helpers import Conditional, Chain, Call, setInterval
from decorators import pipe, catching


LOCKFILE = path.join(path.abspath(path.dirname(__file__)), "lock")
MEMORY = path.join(path.abspath(path.dirname(__file__)), "memory.db")
LOGS_DIR = path.join(path.abspath(path.dirname(__file__)), "logs")

RUNTIME_TASKS = []
CRONTAB = []


@catching(OSError, "Disk write failure.")
def log_write(host, event):
    with open(path.join(LOGS_DIR, slugify(host) + ".txt"), "a+") as log:
        timestamp = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
        log.write(f"[{timestamp}] {event}\n")


def DaemonControl(args):
    @catching(OSError, "Failed to switch to daemon mode. Free up your RAM and retry.")
    def switch_to_daemon_mode():
        if fork():
            exit(0)

    @catching(OSError, "Disk write failure.")
    def create_lock_file():
        with open(LOCKFILE, "w") as lock:
            lock.write(str(getpid()))


    mutual_exclude_flow = Conditional(lambda fst, snd: fst and snd, bool(args["detach"]), bool(args["kill"]))\
        .then(
            Chain(print, "Mutually exclusive flags.")\
                .then(exit, 0)\
                .execute
        )\
        .end()


    detach_flow = Conditional(bool, args["detach"])\
        .then(
            Conditional(path.exists, LOCKFILE)\
                .then(
                    Chain(print, "Daemon is already running.")\
                        .then(exit, 0)\
                        .execute
                )\
                .otherwise(
                    Chain(print, "Switching to daemon mode...")\
                        .then(switch_to_daemon_mode)\
                        .then(create_lock_file)\
                        .execute
                )
        )\
        .end()


    @catching(ValueError, "Lockfile is malformed.")
    @catching(ProcessLookupError, "No process found.", ignoring=True)
    def terminate_daemon():
        with open(LOCKFILE, "r") as lock:
            kill(int(lock.read()), SIGTERM)


    termination_flow = Conditional(bool, args["kill"])\
        .then(
            Conditional(path.exists, LOCKFILE)\
                .then(
                    Chain(terminate_daemon)\
                        .then(print, "Daemon terminated successfully.")\
                        .then(
                            Conditional(path.exists, LOCKFILE)\
                                .then(catching(OSError, "Unable to delete lockfile.")(unlink), LOCKFILE)\
                                .end()
                        )\
                        .execute
                )\
                .otherwise(print, "Lockfile wasn't found")
        )\
        .end()


    Chain(mutual_exclude_flow).then(detach_flow).then(termination_flow).execute()
    return bool(args["kill"]) or False


def DatabaseControl(args):
    connection = sqlite3.connect(MEMORY)
    cursor = connection.cursor()


    create_flow = Chain(
            cursor.execute,
            '''CREATE TABLE IF NOT EXISTS memory (
                host TEXT NOT NULL UNIQUE,
                isdown INTEGER DEFAULT 0 CHECK (isdown == 0 OR isdown == 1),
                interval INTEGER DEFAULT 20 CHECK (interval >= 1)
            );'''
        )\
        .then(connection.commit)\
        .execute


    def clear_flow():
        if not args["clear_hosts"]:
            return

        sel = cursor.execute('''SELECT host FROM memory;''')
        hosts = list(map(lambda row: row[0], sel))
        cursor.execute('''DELETE FROM memory;''')
        connection.commit()

        for host in hosts:
           log_write(host, "REMOVE")

        print("Memory has been cleared.")


    remove_flow = Conditional(lambda fst, snd: fst and snd, bool(args["remove_host"]), not bool(args["clear_hosts"]))\
        .then(
            Chain(cursor.execute, '''DELETE FROM memory WHERE host = ?;''', (args["remove_host"],))\
            .then(connection.commit)\
            .then(log_write, args["remove_host"], "REMOVE")\
            .then(print, f"Deleted {args['remove_host']} from memory.")\
            .execute
        )\
        .end()


    def add_flow():
        if not args["add_host"]:
            return

        if args["interval"]:
            cursor.execute(
                '''INSERT INTO memory (host, interval) VALUES (?, ?) ON CONFLICT(host) DO UPDATE SET interval=excluded.interval;''',
                (args["add_host"], args["interval"])
            )

        else:
            cursor.execute(
                '''INSERT OR IGNORE INTO memory (host) VALUES (?);''',
                (args["add_host"],)
            )

        connection.commit()
        log_write(args["add_host"], f"ADD [INTERVAL={args['interval'] or 20}]")
        print(f"Added {args['add_host']} with interval {args['interval'] or 20} to memory.")


    list_flow = Conditional(bool, args["list_hosts"])\
        .then(
            pipe(
                lambda cur: cur.execute('''SELECT host, interval FROM memory ORDER BY host COLLATE NOCASE ASC;'''),
                lambda selection: map(lambda row: f"{row[0]} — every {row[1]} seconds", selection),
                "\n".join,
                print
            ),
            cursor
        )\
        .end()


    Chain(create_flow).then(clear_flow).then(remove_flow).then(add_flow).then(list_flow).then(connection.close).execute()
    return bool(args["clear_hosts"]) or bool(args["remove_host"]) or bool(args["add_host"]) or bool(args["list_hosts"]) or False


def main(args):
    if not path.exists(LOGS_DIR):
        catching(OSError, "Unable to create directory.")(makedirs)(LOGS_DIR)

    should_exit = DaemonControl(args) or DatabaseControl(args)
    if should_exit:
        exit(0)

    connection = sqlite3.connect(MEMORY, check_same_thread=False)
    cursor = connection.cursor()


    def job(host):
        idx, task = next(
            filter(
                lambda tup: tup[1]["host"] == host,
                enumerate(RUNTIME_TASKS)
            )
        )

        try:
            requests.get(host).raise_for_status()

            if task["isdown"] == 1:
                RUNTIME_TASKS.__setitem__(idx, {**task, "isdown": 0})
                log_write(host, "HOST_UP")
                notification.notify(title="UpDown :)", message=f"{host} is back up again!", timeout=5)

        except requests.exceptions.RequestException:
            if task["isdown"] == 0:
                RUNTIME_TASKS.__setitem__(idx, {**task, "isdown": 1})
                log_write(host, "HOST_DOWN")
                notification.notify(title="UpDown :(", message=f"{host} is down!", timeout=5)


    def update_db():
        if not RUNTIME_TASKS:
            return

        for task_dict in RUNTIME_TASKS:
            cursor.execute('''UPDATE memory SET isdown = ? WHERE host = ?;''', (task_dict["isdown"], task_dict["host"]))

        connection.commit()


    def update_task_list():
        def spawn_cronjob(row_dict):
            return setInterval(
                Call(job, row_dict["host"]),
                row_dict["interval"],
                immediately=True
            )

        row_dicts = pipe(list)(
            map(
                lambda row: dict(zip(["host", "isdown", "interval"], row)),
                cursor.execute('''SELECT host, isdown, interval FROM memory;''')
            )
        )

        for row_dict in row_dicts:
            task = None
            idx = None
            for task_idx, task_dict in enumerate(RUNTIME_TASKS):
                if task_dict["host"] == row_dict["host"]:
                    task = task_dict
                    idx = task_idx

            if not task:
                RUNTIME_TASKS.append(row_dict)
                CRONTAB.append(spawn_cronjob(row_dict))
                log_write(row_dict["host"], "START")

            else:
                if task["interval"] != row_dict["interval"]:
                    if task["interval"] == -1:
                        log_write(row_dict["host"], "START")

                    CRONTAB[idx].cancel()
                    RUNTIME_TASKS.__setitem__(idx, {**task, "interval": row_dict["interval"]})
                    CRONTAB.__setitem__(idx, spawn_cronjob(row_dict))
                    log_write(row_dict["host"], f"APPLY [INTERVAL={row_dict['interval']}]")


        row_hosts = pipe(list)(
            map(lambda sel: sel["host"], row_dicts)
        )

        for task_idx, task_dict in enumerate(RUNTIME_TASKS):
            if task_dict["host"] not in row_hosts and task_dict["interval"] != -1:
                CRONTAB[task_idx].cancel()
                RUNTIME_TASKS.__setitem__(task_idx, {**task_dict, "interval": -1})
                log_write(task_dict["host"], "STOP")


    def log_exit_event():
        sel = cursor.execute('''SELECT host FROM memory;''')
        hosts = map(lambda row: row[0], sel)

        for host in hosts:
            log_write(host, "STOP")


    sync_cronjob = setInterval(
        Chain(update_db).then(update_task_list).execute,
        5,
        immediately=True
    )

    clean_exit_flow = Chain(catching(OSError, "Unable to delete lockfile.", ignoring=True)(unlink), LOCKFILE)\
        .then(sync_cronjob.cancel)\
        .then(list, map(lambda cronjob: cronjob.cancel(), CRONTAB))\
        .then(update_db)\
        .then(log_exit_event)\
        .then(CRONTAB.clear)\
        .then(RUNTIME_TASKS.clear)\
        .then(connection.close)\
        .then(exit, 0)\
        .execute

    signal(SIGTERM, clean_exit_flow)
    signal(SIGINT, clean_exit_flow)


    while True:
        try:
            sleep(5.1)

        except Exception:
            break


    clean_exit_flow()


if __name__ == "__main__":
    parser = ArgumentParser(description="Monitor website state.")
    parser.add_argument("--detach", dest="detach", action="store_true", required=False, help="Start process as a daemon.")
    parser.add_argument("--kill", dest="kill", action="store_true", required=False, help="Terminate daemonized process and exit.")
    parser.add_argument("--add-host", dest="add_host", type=str, required=False, help="Add host to memory and exit.")
    parser.add_argument("--with-interval", dest="interval", type=lambda x: (int(x) >= 1) and int(x) or exit("interval ∉ Nat"), required=False, help="Specify check interval in seconds. Should be used with --add-host.")
    parser.add_argument("--remove-host", dest="remove_host", type=str, required=False, help="Remove host from memory and exit.")
    parser.add_argument("--list-hosts", dest="list_hosts", action="store_true", required=False, help="List hosts in memory and exit.")
    parser.add_argument("--clear-hosts", dest="clear_hosts", action="store_true", required=False, help="Clear memory and exit.")
    parser.set_defaults(detach=False, kill=False, list_hosts=False, clear_hosts=False)
    args = parser.parse_args()

    main(args.__dict__)

