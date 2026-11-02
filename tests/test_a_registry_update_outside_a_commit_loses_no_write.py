"""A read-modify-write of the registry outside a commit loses no other write.

`save_registry` outside a commit session is last-writer-wins, and writers
exist that read, mutate and save outside any transaction -- the lot job's
`deal_berths`, region waves fired after the commit, the editor's post -- so
a charter tick's `land_snapshot` landing between such a read and its save
was reverted by the stale copy while its scheduled rows stayed, and the next
advance re-lived the span on another seed (audit world_charter_core F7,
traced). `registry_update` holds the database write lock across the whole
read-modify-write, the lock `land_snapshot` and `land_presim` already take."""
import threading
import time

from world.charter import normalize_charter
from world.charter_runtime import registry_for, registry_update, save_registry


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Race", "", time.time()))
    save_registry(cid, {"items": {"inn": {"state": normalize_charter({
        "key": "inn", "upkeeps": {}, "posts": {},
        "bodies": {"tam": {"place": "yard"}, "ivo": {"place": "yard"}}})}}})
    return cid


def test_two_updates_that_overlap_both_land(temp_db):
    cid = _story(temp_db)
    inside = threading.Event()
    errors = []

    def first():
        try:
            with registry_update(cid) as registry:
                registry["items"]["inn"]["state"]["bodies"]["tam"][
                    "place"] = "cellar"
                inside.set()
                time.sleep(0.3)
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    def second():
        inside.wait(5)
        try:
            with registry_update(cid) as registry:
                registry["items"]["inn"]["state"]["bodies"]["ivo"][
                    "place"] = "gate"
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=first), threading.Thread(target=second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert not errors, errors
    bodies = registry_for(cid)["items"]["inn"]["state"]["bodies"]
    assert bodies["tam"]["place"] == "cellar"
    assert bodies["ivo"]["place"] == "gate"


def test_an_update_that_raises_writes_nothing(temp_db):
    cid = _story(temp_db)
    try:
        with registry_update(cid) as registry:
            registry["items"]["inn"]["state"]["bodies"]["tam"]["place"] = "x"
            raise RuntimeError("refused")
    except RuntimeError:
        pass
    assert registry_for(cid)["items"]["inn"]["state"]["bodies"]["tam"][
        "place"] == "yard"
