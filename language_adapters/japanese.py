"""Deterministic Japanese Layer-B renderer.

The adapter receives only admitted Percepts. It cannot inspect scene state,
the database, canonical identities, or hidden facts.

Layer B decides only WORDING. Which facts an observer receives was already
settled by Layer A, so this renderer's obligation is to emit every admitted
percept -- a kind it silently drops is a fact the observer earned and does not
get, and it fails with no error anywhere. Four kinds were being dropped and
two more read keys the percepts do not carry; the templates for all of them
were already authored in the pack and simply never called.
"""

from __future__ import annotations

from language_runtime import compositor_text, compositor_value, register_renderer


def _full_stop(text):
    text = str(text or "").strip()
    if not text:
        return ""
    return text if text.endswith(
        ("。", "！", "？", ".", "!", "?", "」", "…", "‥")) else text + "。"


class JapaneseRenderer:
    language = "ja"

    def _text(self, key, **values):
        return compositor_text(key, self.language, **values)

    def _value(self, name):
        return compositor_value(name, self.language)

    # -- individual percept kinds ------------------------------------------

    def _speech(self, p, data, label, prefix):
        if p.fidelity == "fragment":
            return self._text(prefix + "muffled", fragment=data.get("fragment", ""))
        body = data.get("body", "")
        if data.get("conducted"):
            key = (prefix + "conducted") if prefix else "dialogue_conducted"
            return self._text(key, label=label, body=body)
        if prefix:
            return self._text(prefix + "speech", label=label, body=body)
        # Heard-but-unseen and manner/articulation are perceptual FIDELITY,
        # not decoration: they are how the view says the observer could not
        # see who spoke, or could not make the words out cleanly.
        verbs = self._value("dialogue_verbs") or {}
        pair = (verbs.get(str(data.get("volume") or "default"))
                or verbs.get("default") or ("言う", "言う"))
        # [third-person, second-person], as in English: the observer's own
        # speech takes the second form.
        verb = str(pair[1] if label == "あなた" or p.source_label == "you"
                   else pair[0])
        # An enum key, mapped through the pack -- never printed raw. Passing
        # it through emitted the literal English token into Japanese prose:
        # 「レイヤはslurred言う。」
        articulation = str((self._value("articulation") or {}).get(
            str(data.get("articulation") or ""), ""))
        if not data.get("can_see"):
            return self._text("dialogue_unseen", label=label, verb=verb,
                              articulation=articulation, body=body)
        return self._text("dialogue_visible", label=label,
                          manner=self._tone(data.get("tone")),
                          articulation=articulation, verb=verb, body=body)

    def _tone(self, tone):
        tone = str(tone or "").strip()
        if not tone:
            return ""
        behavior = self._value("tone_behavior_words") or ()
        key = "tone_behavior" if tone in set(behavior) else "tone_adjective"
        return self._text(key, tone=tone)

    def _environment(self, data, prefix):
        parts = []
        if data.get("room_name"):
            parts.append(self._text(prefix + "room", room=data["room_name"]))
        notes = str(data.get("room_notes") or "").strip()
        if notes:
            parts.append(_full_stop(notes))
        light = str(data.get("light") or "").casefold()
        if light in ("dim", "low"):
            parts.append(self._text(prefix + "light_dim"))
        elif light in ("dark", "none", "pitch_black", "black"):
            parts.append(self._text(prefix + "light_dark"))
        return "".join(parts)

    def _presence(self, p, data, label, prefix):
        if prefix:
            return self._text(prefix + "presence", label=label)
        tiers = self._value("tier_phrases") or {}
        tier = str(tiers.get(str(data.get("tier")), tiers.get("default", "")))
        side = data.get("side")
        sides = self._value("side_words") or {}
        side_clause = (self._text("side", side=sides.get(side, side))
                       if side in ("left", "right") else "")
        if not tier:
            return self._text("presence", label=label)
        # One clause, so distance and side are grammatical rather than
        # concatenated after the name.
        return self._text("presence_placed", label=label,
                          side=side_clause, tier=tier)

    def _body_part(self, p, data, label):
        """A body's own anatomy. Dropped entirely before, so an authored tail,
        wings or extra limbs were invisible in every Japanese view."""
        count = data.get("count")
        kind = str(data.get("part") or "").strip()
        if not kind:
            return ""
        word = self._count_phrase(count, kind)
        whose = "あなた" if p.source_label == "you" else label
        aspect, at = data.get("aspect"), data.get("at")
        aspects = self._value("aspect_words") or {}
        aspect_word = aspects.get(aspect, aspect)
        if aspect == "sides":
            where = self._text("body_part_where_sides", whose=whose, at=at)
        elif aspect in ("left", "right"):
            where = self._text("body_part_where_side", aspect=aspect_word,
                               whose=whose, at=at)
        else:
            where = self._text("body_part_where_aspect", aspect=aspect_word,
                               whose=whose, at=at)
        sentence = self._text("body_part", where=where, count=word, part=kind)
        # Each becomes its own sentence. Joined with 読点 before, which left a
        # 連体形 description ("膜のような") modifying nothing.
        description = str(data.get("description") or "").strip()
        if description:
            sentence += description.rstrip("。.") + "。"
        if data.get("tucked"):
            sentence += self._text("body_part_tucked")
        return sentence

    def _pose(self, p, data, label, prefix):
        """Built from posture/support/relative_to, the fields English uses.

        It read a `detail` key the composer never sets, so a pose carrying
        support or a spatial relation rendered as its posture alone -- or as
        nothing at all.
        """
        posture = str(data.get("posture") or data.get("detail") or "").strip()
        parts = []
        other = str(data.get("relative_to") or "").strip()
        if other:
            relation = str(data.get("relation") or "").strip()
            parts.append(relation + other if relation
                         else self._text("pose_relation", other=other))
        support = str(data.get("support") or "").strip()
        if support:
            parts.append(self._text("pose_support", support=support))
        constraint = str(data.get("constraint") or "").strip()
        if constraint:
            parts.append(constraint)
        # Predicate LAST. Built in English order before, which produced
        # 「ひざまずいて床の上に壁に接して」 -- locatives trailing the verb and
        # nothing terminating the sentence.
        parts.append(posture)
        clause = "".join(part for part in parts if part).strip()
        # A 〜て/〜で form is a continuative, not a sentence.
        if clause.endswith(("て", "で")):
            clause += "いる"
        return self._text(prefix + "pose", label=label,
                          detail=self._past(clause, bool(prefix))) if clause else ""

    @staticmethod
    def _past(clause, episode):
        """Put a rendered clause into the past, for memory episodes.

        A memory saying 「尻尾が生えている」 is a claim about NOW. The tense is
        chosen where the clause is built, exactly as the English renderer's
        `_render_pose(past=...)` does, rather than regex-ed out of finished
        prose afterwards -- which would also reach into authored story text.
        """
        if not episode or not clause:
            return clause
        for present, past in (("ている", "ていた"), ("でいる", "でいた"),
                              ("がある", "があった"), ("にいる", "にいた"),
                              ("である", "であった")):
            if clause.endswith(present):
                return clause[:-len(present)] + past
        return clause

    def _count_phrase(self, count, part):
        """How many, in the counter the NOUN takes.

        Japanese picks 本 / 枚 / つ by what is being counted, so a single
        generic counter reads as a children's book ("二つの尻尾"). Singular
        is UNMARKED -- 「一つの尻尾」 is actively wrong -- and above four a
        vague quantifier is what a writer uses.
        """
        key = str(count)
        counters = self._value("body_part_counters") or {}
        numerals = self._value("counter_numerals") or {}
        suffix = next((c for noun, c in counters.items() if noun in part), None)
        if suffix and key in numerals:
            if key == "1":
                return ""
            return f"{numerals[key]}{suffix}"
        return str((self._value("count_generic") or {}).get(key, key))

    def _body_state(self, data, label, prefix):
        """Reads posture/activity/held_items -- the keys the percept actually
        carries. It read `detail`/`state`, which are never set, so every
        Japanese body state rendered as a dangling `{label}の状態：`."""
        parts = []
        if data.get("posture"):
            parts.append(self._text(prefix + "posture", value=data["posture"]))
        if data.get("activity"):
            parts.append(self._text(prefix + "activity", value=data["activity"]))
        if data.get("held_items"):
            parts.append(self._text(prefix + "held",
                                    items="、".join(data["held_items"])))
        if parts:
            return "".join(parts)
        detail = str(data.get("detail") or data.get("state") or "").strip()
        return self._text(prefix + "body_state", label=label,
                          detail=detail) if detail else ""

    def _body_region(self, p, data, label, prefix):
        place = str(data.get("place") or "").strip()
        detail = str(data.get("detail") or data.get("description") or "").strip()
        if not place or not detail:
            return ""  # both halves required, as in English
        if prefix:
            return self._text(prefix + "body_region", label=label, detail=detail)
        subject = (self._text("exposed_self", place=place)
                   if p.source_label == "you"
                   else self._text("exposed_other", label=label, place=place))
        return self._text("exposed_detail", subject=subject,
                          detail=detail.rstrip("。."))

    def _scent(self, data, label, prefix):
        """Three shapes, the same three the percept chose between: the smell
        and whose it is, the smell alone, or a faint thing from beyond. A
        muffled scent never reaches the attributed template -- the percept
        carries no label to put in it."""
        scent = str(data.get("scent") or "").strip()
        if not scent:
            return ""
        if data.get("level") == "muffled":
            return self._text(prefix + "scent_faint", scent=scent)
        if data.get("attributed") and label:
            return self._text(prefix + "scent_source", label=label,
                              scent=scent)
        return self._text(prefix + "scent_air", scent=scent)

    def _sentence(self, percept, *, episode=False):
        p = percept
        label = str(p.source_label or "")
        data = p.data or {}
        prefix = "episode_" if episode else ""
        if p.kind == "speech":
            return self._speech(p, data, label, prefix)
        if p.kind == "environment":
            return self._environment(data, prefix)
        if p.kind == "presence":
            return self._presence(p, data, label, prefix)
        if p.kind == "appearance":
            description = data.get("description") or ""
            return self._text(prefix + "appearance", label=label,
                              description=description) if description else ""
        if p.kind == "act":
            surface = str(data.get("surface") or "").strip()
            return self._text(prefix + "act", label=label,
                              action=surface) if surface else ""
        if p.kind == "crossing":
            direction = "arrived" if data.get("direction") == "arrived" else "departed"
            return self._text(prefix + direction, label=label)
        if p.kind == "pose":
            return self._pose(p, data, label, prefix)
        if p.kind == "scent":
            return self._scent(data, label, prefix)
        if p.kind in ("sensation", "substance", "ambient"):
            return _full_stop(data.get("clause") or data.get("text")
                              or data.get("desc") or "")
        if p.kind == "body_part":
            return self._past(self._body_part(p, data, label).rstrip("。"),
                              bool(prefix))
        if p.kind == "body_region":
            return self._body_region(p, data, label, prefix)
        if p.kind == "body_state":
            return self._body_state(data, label, prefix)
        if p.kind == "residue":
            from agents.common import _compose_residue_view
            return _compose_residue_view(
                data.get("level"), targeted=data.get("targeted", False),
                loud_event=data.get("loud_event", False), pain=data.get("pain", False))
        return ""

    # -- whole views --------------------------------------------------------

    def render_view(self, percepts, *, mode="character",
                    prev_standing=frozenset(), prev_described=frozenset(),
                    full_render=False):
        from agents import composer
        from agents.composer import RenderedView

        percepts = list(percepts or [])
        standing_keys = {p.dedupe_key for p in percepts
                         if p.order_key is None and p.dedupe_key}
        described = set(prev_described or ())

        # The non-awake floor. If any residue percept is present the view IS
        # the residue and nothing else -- a mind below waking does not also
        # receive the room, the dialogue and the arrivals. English short-
        # circuits here; without it this depended on three call sites choosing
        # to assign rather than append, which is the opposite of a floor.
        residue = [p for p in percepts if p.kind == "residue"]
        if residue:
            spans = []
            for p in residue:
                sentence = _full_stop(self._sentence(p))
                if sentence:
                    spans.append((p, sentence))
            return RenderedView(
                text="".join(sentence for _, sentence in spans), spans=spans,
                standing_keys=standing_keys, described=described)

        # THE VERDICT IS SHARED, THE WORDING IS THE PACK'S. This adapter
        # carried its own copy of the player delta rule and it had already
        # drifted once -- `prev_described` was accepted and never consulted,
        # so a body's full appearance was re-described from scratch every
        # beat. Which percepts a view may carry is an information decision
        # and belongs to one function; how the sentence reads is the pack's.
        player = mode == "player"
        verdicts = composer.standing_verdicts(
            percepts, prev_standing, prev_described) if player else {}
        presence_leads = player and any(
            composer.leads_the_beat(
                p, verdicts.get(p.dedupe_key, "first"), prev_standing)
            for p in percepts if p.kind == "presence")

        beat, background = [], []
        seen = set()
        ordered = sorted(
            enumerate(percepts),
            key=lambda item: (item[1].order_key is not None,
                              item[1].order_key if item[1].order_key is not None
                              else item[0]))
        for _, p in ordered:
            if p.dedupe_key and p.dedupe_key in seen:
                continue
            seen.add(p.dedupe_key)
            verdict = verdicts.get(p.dedupe_key, "first")
            if player and p.order_key is None and not full_render:
                if p.kind == "appearance":
                    if (verdict == "unchanged"
                            and not composer.appearance_delta(p)):
                        continue
                    if (verdict == "reearn" and not (p.data or {}).get("reearn")
                            and not (p.data or {}).get("force")):
                        continue
                elif (p.dedupe_key in (prev_standing or ())
                      and p.kind not in composer.ACTIVE_STANDING_KINDS):
                    continue
            source_key = str((p.data or {}).get("source_key") or "")
            sentence = _full_stop(self._sentence(p))
            if not sentence:
                continue
            # Character mode keeps the sequence it always had: standing
            # state in percept order, then the beat. Only the player view
            # partitions.
            leads = player and (
                p.order_key is not None
                or composer.leads_the_beat(p, verdict, prev_standing)
                or (p.kind == "presence" and presence_leads))
            if leads:
                beat.append((composer.as_beat(p)
                             if p.order_key is None else p, sentence))
            else:
                background.append((p, sentence))
            if p.kind == "appearance" and source_key:
                described.add(source_key)
        # WHERE the halves sit is the composer's rule, not the pack's. This
        # adapter spelled it itself and got it wrong: it emitted the beat in
        # the order it iterated -- standing before events -- so a Japanese
        # player view opened on the changed pose where English opened on the
        # act that moved it.
        spans = (composer.player_view_order(beat + background) if player
                 else beat + background)
        return RenderedView(
            text="".join(sentence for _, sentence in spans), spans=spans,
            standing_keys=standing_keys, described=described)

    def render_episode(self, percepts, *, prev_standing=frozenset(),
                       prev_described=frozenset()):
        percepts = list(percepts or [])
        residue = [p for p in percepts if p.kind == "residue"]
        if residue:  # the same floor as render_view
            sentences = [s for s in (_full_stop(self._sentence(p, episode=True))
                                     for p in residue) if s]
            content = "".join(dict.fromkeys(sentences))
            return content, (sentences[0][:240] if sentences else ""), []
        selected = [p for p in percepts if p.order_key is not None]
        selected.extend(
            p for p in percepts
            if p.order_key is None and p.dedupe_key not in (prev_standing or ())
            and (p.kind != "appearance" or (p.data or {}).get("force")
                 or str((p.data or {}).get("source_key") or "")
                 not in (prev_described or ())))
        if not selected:
            return "", "", []
        # An episode is the character's own memory, so second person becomes
        # first. The English renderer does this and the adapter did not, so a
        # Japanese memory mixed 「あなたは立っている。」 with 「私は中庭にいた。」
        from agents.composer import _first_person
        sentences = [_full_stop(_first_person(self._sentence(p, episode=True)))
                     for p in selected]
        sentences = [s for s in sentences if s]
        content = "".join(dict.fromkeys(sentences))
        # Generic labels are descriptors, not entities. Indexing "a voice" or
        # "an indistinct figure" as a memory entity pollutes recall with rows
        # that name nobody; English filters them and this did not.
        generic = {str(g) for g in (self._value("generic_labels") or ())}
        entities = []
        for p in selected:
            label = str(p.source_label or "")
            if label and label not in entities and label not in generic:
                entities.append(label)
        return content, (sentences[0][:240] if sentences else ""), entities[:16]


register_renderer("japanese", JapaneseRenderer())
