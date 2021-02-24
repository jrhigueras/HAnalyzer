#!/usr/bin/env python3.8
import argparse
import curses
import curses.panel
import requests
import sys
import ThreadedWorkers
import time
from queue import Queue
from requests.models import Response

threads = []
stdscr = None
nodes = {}
sums = {}
shutting_down = False


def req(url: str, method: str = "GET", match_header: str = "X-Node-ID"):
    try:
        r = requests.request(method=method, url=url)
    except Exception:
        return
    try:
        json = r.json()
    except Exception:
        json = {}

    node = r.headers.get(match_header) or json.get("node")

    if not node:
        node = "Undefined"

    with ThreadedWorkers.LOCK:
        curses_add_response(node, r)


def threaded_call(q: Queue, function: callable, parameters: tuple = tuple()):
    q.put({
        "function": function,
        "parameters": parameters
    })


def awake_threads(n: int, q: Queue, quiet: bool = False) -> list:
    threads = []
    for i in range(n):
        thread = ThreadedWorkers.Queued(thread_id=i, q=q, quiet=quiet)
        thread.start()
        threads.append(thread)
    return threads


def shutdown(clean=True):
    global shutting_down
    time.sleep(1)
    for thread in threads:
        if clean:
            thread.wait()
        thread.exit = True
        thread.wait()
    curses_close()
    print("[MAIN] Shutting down...")
    sys.exit(0)


def curses_add_response(node: str, r: Response):
    global nodes, sums
    status_code = r.status_code

    node_data = nodes.get(node)
    if not node_data:
        node_data = {
            "status_codes": {}
        }
        nodes[node] = node_data

    status_codes = node_data.get('status_codes')
    idx = list(nodes.keys()).index(node)

    if status_code not in status_codes.keys():
        status_codes[status_code] = 1
        if status_code in sums:
            sums[status_code] += 1
        else:
            sums[status_code] = 1
    else:
        status_codes[status_code] += 1
        sums[status_code] += 1

    v = str(status_codes[status_code])

    y = 2
    x = 0
    # Method:
    txt = f"Method: {r.request.method}\n   URL: {r.url}"
    stdscr.addstr(y, x, txt)
    # Nodes:
    y += 3
    stdscr.addstr(y, x, "Node ID:" + " " * 45 + "Status code:")
    stdscr.addstr(y + idx + 2, x, node + ":")

    # Status codes:
    idy = list(sums.keys()).index(status_code) + 1
    x = 60 + idy * 9
    stdscr.addstr(y, x, str(status_code))
    stdscr.addstr(y + idx + 2, x + 1 - len(v) // 2, v)

    # Totals:
    y = y + len(nodes) + 3
    x = 58
    stdscr.addstr(y - 1, 0, " " * curses.COLS)
    stdscr.addstr(y, x, "Totals:")
    idy = 1
    for n in sums.values():
        x = 60 + idy * 9
        v = str(n)
        stdscr.addstr(y, x + 1 - len(v) // 2, v)
        idy += 1
    stdscr.refresh()


def curses_close():
    global stdscr
    try:
        txt = "Press any key to exit..."
        stdscr.addstr(
            curses.LINES - 1,
            curses.COLS // 2 - len(txt) // 2,
            txt,
            curses.A_BLINK | curses.A_BOLD)
        stdscr.refresh()
        stdscr.getch()
        curses.nocbreak()
        curses.echo()
        curses.curs_set(1)
        curses.endwin()
        stdscr = None
    except Exception:
        pass


def curses_init():
    global stdscr
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    curses.curs_set(0)
    stdscr.clear()
    txt = "HAnalyzer - High-Availability & Load-Balancing analyzer"
    stdscr.addstr(0, curses.COLS // 2 - len(txt) // 2, txt)
    stdscr.refresh()


def main():
    global threads
    q = Queue(1000)
    print("[MAIN] Awaking threads...")
    threads = awake_threads(n=args.threads, q=q, quiet=args.quiet)
    print("[MAIN] Starting curses")
    curses_init()

    if args.requests == -1:
        args.requests = float("inf")

    while args.requests > 0:
        args.requests -= 1
        threaded_call(q, req, (args.url, args.method, args.header))

    shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="It sends several probes in order to test High-Availability and Load-Balancing.",
    )
    parser.add_argument(
        "url",
        metavar="URL",
        type=str,
        help="The URL you'd like to perform the testing."
    )
    parser.add_argument(
        "-t", "--threads",
        action="store",
        help="Number of threads to launch.\n-1 to run forever",
        type=int,
        default=1
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Hide threads output.",
        default=False
    )
    parser.add_argument(
        "-r", "--requests",
        action="store",
        help="Number of request to perform.",
        type=int,
        default=10000
    )
    parser.add_argument(
        "-H", "--header",
        action="store",
        help="Header to match different node",
        type=str,
        default="X-Node-ID"
    )
    parser.add_argument(
        "-X", "--method",
        action="store",
        help="Specify the method to use",
        type=str,
        default="GET"
    )

    args = parser.parse_args()
    try:
        main()
    except KeyboardInterrupt:
        shutdown(False)
