"""
The click command tree Typer builds from a Typer app is cached per app and only
rebuilt when something is registered on it. These tests pin the cache's
correctness, its invalidation, and its behavior under parallel use.
"""

import asyncio
import json
import threading
from contextlib import contextmanager
from uuid import uuid4

from django.core.management import call_command
from django.test import SimpleTestCase

from django_typer import management as mgmt
from django_typer.management import Finalizer, get_command, get_typer_command


@contextmanager
def count_builds():
    """Count real click tree builds while the block runs."""
    counter = {"n": 0}
    real = mgmt._build_click_command

    def counting(*args, **kwargs):
        counter["n"] += 1
        return real(*args, **kwargs)

    mgmt._build_click_command = counting
    try:
        yield counter
    finally:
        mgmt._build_click_command = real


def register(command_cls, group=None):
    """Register a new command with a unique name and return (cli_name, value)."""
    value = f"dyn_{uuid4().hex[:8]}"

    def dynamic(self):
        return value

    dynamic.__name__ = value
    (group or command_cls).command()(dynamic)
    return value.replace("_", "-"), value


class CommandTreeCacheTests(SimpleTestCase):
    def test_tree_built_once_per_app(self):
        get_typer_command(type(get_command("basic")).typer_app)  # warm
        with count_builds() as builds:
            for i in range(5):
                result = json.loads(call_command("basic", f"a{i}", "b"))
                self.assertEqual(result["arg1"], f"a{i}")
            cmd = get_command("basic")
            cmd.create_parser("manage.py", "basic")
            cmd.command_tree  # noqa: B018
        self.assertEqual(builds["n"], 0)

    def test_instance_and_class_share_the_tree(self):
        cmd = get_command("basic")
        # on the instance typer_app is a proxy - it must resolve to the same entry
        self.assertIs(
            get_typer_command(cmd.typer_app), get_typer_command(type(cmd).typer_app)
        )

    def test_registration_invalidates_root(self):
        from tests.apps.test_app.management.commands.cache_target import Command

        before = get_typer_command(Command.typer_app)
        self.assertIs(before, get_typer_command(Command.typer_app))

        name, value = register(Command)
        after = get_typer_command(Command.typer_app)
        self.assertIsNot(before, after)
        self.assertIn(name, after.commands)
        self.assertEqual(call_command("cache_target", name), value)

        # registering on a sub-app must invalidate the root's tree as well
        name, value = register(Command, group=Command.grp)
        after_sub = get_typer_command(Command.typer_app)
        self.assertIsNot(after, after_sub)
        self.assertIn(name, after_sub.commands["grp"].commands)
        self.assertEqual(call_command("cache_target", "grp", name), value)

    def test_finalizer_and_help_change_the_signature(self):
        from tests.apps.test_app.management.commands.cache_target import Command

        app = Command.typer_app
        before = mgmt._app_signature(app)

        original = app.info.result_callback
        app.info.result_callback = Finalizer(lambda self, result: result)
        try:
            self.assertNotEqual(before, mgmt._app_signature(app))
        finally:
            app.info.result_callback = original
        self.assertEqual(before, mgmt._app_signature(app))

        original = app.info.help
        app.info.help = "changed"
        try:
            self.assertNotEqual(before, mgmt._app_signature(app))
        finally:
            app.info.help = original
        self.assertEqual(before, mgmt._app_signature(app))

    def test_inherited_command_has_its_own_tree(self):
        from tests.apps.test_app.management.commands.cache_target import Command

        parent_tree = get_typer_command(Command.typer_app)

        class Child(Command):
            @mgmt.command()
            def only_on_child(self):
                return "child"

        child_tree = get_typer_command(Child.typer_app)
        self.assertIsNot(parent_tree, child_tree)
        self.assertIn("only-on-child", child_tree.commands)
        self.assertNotIn("only-on-child", parent_tree.commands)
        # the parent's entry was not disturbed by building the child
        self.assertIs(parent_tree, get_typer_command(Command.typer_app))

    def test_change_during_build_is_not_cached_stale(self):
        from tests.apps.test_app.management.commands.cache_target import Command

        app = Command.typer_app
        baseline_help = get_typer_command(app).help  # warm
        with mgmt._click_commands_lock:
            mgmt._click_commands.pop(app, None)
        original = app.info.help

        real = mgmt._build_click_command

        def build_while_changed(*args, **kwargs):
            # another thread changes the app while this build is in flight, so
            # the tree we build reflects a state the caller never fingerprinted
            app.info.help = "transient help"
            return real(*args, **kwargs)

        mgmt._build_click_command = build_while_changed
        try:
            first = get_typer_command(app)
        finally:
            mgmt._build_click_command = real
        self.assertEqual(first.help, "transient help")

        # ... and then restores it, so the original signature describes the app
        # again. That tree must not be served for it.
        app.info.help = original
        with count_builds() as builds:
            second = get_typer_command(app)
        self.assertEqual(builds["n"], 1)
        self.assertIsNot(first, second)
        self.assertEqual(second.help, baseline_help)
        self.assertIs(second, get_typer_command(app))

    def test_parallel_fresh_instances(self):
        workers, iterations = 16, 20
        barrier = threading.Barrier(workers)
        results: dict[tuple[int, int], str] = {}
        errors: list[BaseException] = []

        def worker(i: int):
            try:
                barrier.wait()
                for j in range(iterations):
                    results[(i, j)] = call_command(
                        "basic", f"t{i}", f"j{j}", arg4=i * 100 + j
                    )
            except BaseException as err:
                errors.append(err)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(results), workers * iterations)
        for (i, j), result in results.items():
            parsed = json.loads(result)
            self.assertEqual(parsed["arg1"], f"t{i}")
            self.assertEqual(parsed["arg2"], f"j{j}")
            self.assertEqual(parsed["arg4"], i * 100 + j)

    def test_parallel_first_use_shares_one_build(self):
        app = type(get_command("groups")).typer_app
        with mgmt._click_commands_lock:
            mgmt._click_commands.pop(app, None)

        workers = 8
        barrier = threading.Barrier(workers)
        trees: list[object] = []

        def worker():
            barrier.wait()
            trees.append(get_typer_command(app))

        with count_builds() as builds:
            threads = [threading.Thread(target=worker) for _ in range(workers)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(builds["n"], 1)
        self.assertEqual(len(trees), workers)
        self.assertTrue(all(tree is trees[0] for tree in trees))

    def test_registration_while_others_execute(self):
        from tests.apps.test_app.management.commands.cache_target import Command

        stop = threading.Event()
        errors: list[BaseException] = []
        executed = {"n": 0}

        def runner():
            try:
                while not stop.is_set():
                    self.assertEqual(call_command("cache_target", "cmd1"), "cmd1")
                    self.assertEqual(
                        call_command("cache_target", "grp", "sub1"), "sub1"
                    )
                    executed["n"] += 1
            except BaseException as err:
                errors.append(err)

        threads = [threading.Thread(target=runner) for _ in range(4)]
        for thread in threads:
            thread.start()
        try:
            for _ in range(10):
                name, value = register(Command)
                self.assertEqual(call_command("cache_target", name), value)
                name, value = register(Command, group=Command.grp)
                self.assertEqual(call_command("cache_target", "grp", name), value)
        finally:
            stop.set()
            for thread in threads:
                thread.join()

        self.assertEqual(errors, [])
        self.assertGreater(executed["n"], 0)

    def test_async_tasks(self):
        async def main():
            return await asyncio.gather(
                *[
                    asyncio.to_thread(call_command, "basic", f"a{i}", "b", arg4=i)
                    for i in range(16)
                ]
            )

        results = asyncio.run(main())
        for i, result in enumerate(results):
            parsed = json.loads(result)
            self.assertEqual(parsed["arg1"], f"a{i}")
            self.assertEqual(parsed["arg4"], i)

    def test_completion_uses_the_cache(self):
        # warm both completion targets, then no completion should build anything
        call_command("shellcompletion", "--shell", "bash", "complete", "basic ")
        call_command("shellcompletion", "--shell", "bash", "complete", "groups math ")
        with count_builds() as builds:
            for _ in range(3):
                call_command("shellcompletion", "--shell", "bash", "complete", "basic ")
                call_command(
                    "shellcompletion", "--shell", "bash", "complete", "groups math "
                )
        self.assertEqual(builds["n"], 0)
