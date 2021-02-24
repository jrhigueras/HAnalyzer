import threading
import queue
import time
import gc

LOCK = threading.RLock()


class Generic(threading.Thread):
    callbacks = {
        "onStop": [],
        "onStart": []
    }

    def __init__(self, thread_id, quiet=True, target=None, args=(), kwargs={}):
        try:
            threading.Thread.__init__(self, target=target, args=args, kwargs=kwargs)
        except Exception:
            print("Invalid call")
            return
        self.thread_id = thread_id
        self.quiet = quiet

    def pr(self, str):
        if not self.quiet:
            print("[THREAD-{:02d}] {}".format(self.thread_id, str), flush=True)

    def register_callback(self, event, f):
        if not callable(f):
            return False
        if event not in self.callbacks.keys():
            return False
        self.callbacks[event].append(f)

    def run(self):
        if len(self.callbacks['onStart']) > 0:
            for f in self.callbacks['onStart']:
                f()
        super().run()

    def stop(self):
        for f in self.callbacks['onStop']:
            f()


class Queued(Generic):
    quiet = True
    exit = False

    def __init__(self, thread_id, q, quiet=True):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.q = q
        self.quiet = quiet
        self.sleeping = True
        self.sleeping_iters = 0
        self.sleeptime = 0
        self.pr("Spawned!")

    def pr(self, str):
        if not self.quiet:
            print("[THREAD-{:02d}] {}".format(self.thread_id, str), flush=True)

    def stop(self):
        self.exit = True
        self.pr("Stopping...")
        super().stop()

    def debug(self):
        print(locals())
        print(globals())
        print(self)

    def run(self):
        super().run()
        while not self.exit:
            if self.q.empty():
                if self.sleeping is False:
                    self.pr("No work, sleeping...")
                    self.sleeping = True
                    self.sleeping_iters = 0
                self.sleeping_iters += 1

                self.sleeptime = self.sleeping_iters / 20
                if self.sleeptime < .1:
                    self.sleeptime = .1
                elif self.sleeptime > 1:
                    self.sleeptime = 1
                time.sleep(self.sleeptime)
                continue
            try:
                self.workload = self.q.get()
            except queue.Empty:
                continue

            if self.sleeping is True:
                self.sleeping = False

            f = self.workload['function']
            p = self.workload['parameters']
            f(*p)
            self.q.task_done()
            del f, p
            del self.workload['function'], self.workload['parameters']
            self.workload = None
            del self.workload
            gc.collect()
        self.pr("Exited")

    def wait(self):
        while not self.sleeping and not self.exit:
            time.sleep(.5)
