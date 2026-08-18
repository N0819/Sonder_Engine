"""A router alias is not a model, and the engine has to say which answered.

THE GAP. `agent_models` points director, character and narrator at
`accounts/fireworks/routers/glm-5p2-fast` — a ROUTER, which dispatches to
whatever backing model it picks per request. The engine sent the alias and
never read the `model` field the provider returns, so a substitution to a
materially different model — different speed, different reliability — left no
trace in any log, metric or stored turn.

It cost a measurement immediately. A latency investigation into whether the
Director should be decomposed produced per-stage medians that were an artefact
of which backing model happened to answer: a fast-but-error-prone model
deflated the very stage under investigation, and the conclusion inverted once
that was known. Every wall-clock number in the corpus is a mixture over an
unrecorded variable.

`usage` was already read back from the same response for exactly this kind of
reason — to make caching observable rather than assumed. The model's own
identity was sitting unread beside it.
"""

from __future__ import annotations

from llm import providers


def _reset():
    providers._SERVED_SEEN.clear()


def test_a_substitution_is_reported(monkeypatch):
    said = []
    monkeypatch.setattr(providers._logger, "warning",
                        lambda msg, *a: said.append(msg % a if a else msg))
    _reset()
    providers._note_served_model(
        "director", "accounts/fireworks/routers/glm-5p2-fast", "glm-4.7")
    assert len(said) == 1
    assert "glm-4.7" in said[0] and "glm-5p2-fast" in said[0]
    assert "director" in said[0]


def test_the_model_asked_for_answering_is_silent(monkeypatch):
    said = []
    monkeypatch.setattr(providers._logger, "warning",
                        lambda msg, *a: said.append(msg))
    _reset()
    providers._note_served_model("director", "glm-5.2", "glm-5.2")
    assert said == []


def test_a_provider_that_says_nothing_is_not_an_accusation(monkeypatch):
    """Not every provider echoes the field, and silence is not substitution."""
    said = []
    monkeypatch.setattr(providers._logger, "warning",
                        lambda msg, *a: said.append(msg))
    _reset()
    for served in (None, "", "   "):
        providers._note_served_model("narrator", "some-model", served)
    assert said == []


def test_it_says_so_once_per_substitution_not_once_per_call(monkeypatch):
    """A line per call would bury the signal in the thing it is reporting on.

    Distinct substitutions still each get a line — a router that starts
    dispatching somewhere new is news again.
    """
    said = []
    monkeypatch.setattr(providers._logger, "warning",
                        lambda msg, *a: said.append(msg % a if a else msg))
    _reset()
    for _ in range(25):
        providers._note_served_model("director", "router-alias", "glm-4.7")
    assert len(said) == 1
    providers._note_served_model("director", "router-alias", "glm-5.2")
    assert len(said) == 2
    providers._note_served_model("narrator", "router-alias", "glm-4.7")
    assert len(said) == 3


def test_the_metrics_line_names_the_model_that_answered(monkeypatch):
    """The point of the whole change: a metrics row must describe the call
    that HAPPENED, or per-model timings cannot be separated after the fact."""
    logged = {}
    monkeypatch.setattr("core.logging_utils.log_llm_call",
                        lambda role, model, **kw: logged.update(
                            role=role, model=model, **kw))
    monkeypatch.setattr(providers._logger, "warning", lambda *a, **k: None)
    _reset()
    providers._log_usage("director", "router-alias", 0.0,
                         {"prompt_tokens": 10, "completion_tokens": 2},
                         served="glm-4.7")
    assert logged["model"] == "glm-4.7"
    assert logged["role"] == "director"


def test_without_a_served_name_the_requested_one_stands(monkeypatch):
    logged = {}
    monkeypatch.setattr("core.logging_utils.log_llm_call",
                        lambda role, model, **kw: logged.update(model=model))
    _reset()
    providers._log_usage("narrator", "asked-for", 0.0, {}, served=None)
    assert logged["model"] == "asked-for"


def test_every_response_path_reads_the_field():
    """Four non-streaming call sites and four streaming ones. The streaming
    branch is the one the pipeline actually runs — capturing only in the
    non-streaming path would have left substitution invisible exactly where
    it counts, which is how reasoning capture stayed dead for a release.
    """
    source = open(providers.__file__).read()
    assert source.count("served=parsed.get(\"model\")") == 4
    assert source.count("served=served") == 4
    # ...and the stream reads it off the chunks rather than guessing.
    assert source.count("served = str(j.get(\"model\") or \"\").strip()") == 2
