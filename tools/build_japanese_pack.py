"""Seed the bundled Japanese beta pack from the English reference shape.

A SEEDER, not a build step. The Japanese pack is partly irreplaceable source:
its prompt card is model-drafted and hand-reviewed, and its compositor and
linguistics cards carry corrections that exist nowhere else. Re-running this
over a populated pack therefore DESTROYS work -- measured at 74 reverted UI
translations, plus every hand-fixed regex anchor and template.

So it refuses to overwrite an existing pack unless told to. Use it to start a
new language, or with --overwrite when you have decided the generated shape
should win and you have the diff in front of you.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "language_packs" / "en"
JA = ROOT / "language_packs" / "ja"

_parser = argparse.ArgumentParser(description=__doc__)
_parser.add_argument(
    "--overwrite", action="store_true",
    help="replace an existing pack's generated surfaces (destroys hand edits)")
_args = _parser.parse_args()
if (JA / "manifest.json").exists() and not _args.overwrite:
    raise SystemExit(
        "language_packs/ja already exists. This tool regenerates the "
        "compositor and linguistics cards from the English shape and would "
        "discard hand corrections in them. Re-run with --overwrite once you "
        "have reviewed `git diff language_packs/ja`.")
(JA / "cards").mkdir(parents=True, exist_ok=True)


def load(relative):
    return json.loads((EN / relative).read_text(encoding="utf-8"))


def save(relative, value):
    path = JA / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


save("manifest.json", {
    "schema_version": 1,
    "id": "ja",
    "name": "Japanese",
    "native_name": "日本語",
    "direction": "ltr",
    "version": "0.2.0-beta",
    "translation_status": "model-draft",
    "fallback": "en",
    "ui": True,
    "story": True,
    "adapter": "japanese",
    "coverage": {
        "authoring": True,
        "compositor": True,
        "deterministic_linguistics": True,
        "system_prompts": True,
        "ui": True,
    },
    "cards": ["authoring", "compositor", "linguistics", "system_prompts"],
})

save("prompt_policy.json", {
    "common": (
        "言語およびスキーマ契約: 読者に見せるすべての自然言語の値は、"
        "文脈と登場人物の口調に合う自然な日本語で書くこと。エンジンのプロトコルは、"
        "物語の言語にかかわらず正規の英語のままである。指定されたJSONキー、"
        "スキーマフィールド、列挙値、識別子、ステップ名、身体部位ID、操作名を"
        "一字も翻訳・改名・活用しないこと。JSON形式が指定されている場合は必ず"
        "構造的に正しいJSONを返し、翻訳するのは自由記述の自然言語値だけにすること。"
    ),
    "roles": {
        "narrator": "説明臭い直訳調を避け、読みやすい現代日本語の小説文として書くこと。",
        "character": "台詞と内面は人物ごとの語彙、敬語、距離感、一人称を一貫させること。",
        "director_interpret": "日本語の助詞、省略された主語、語順を踏まえて宣言を解釈すること。",
        "director_resolve_lean": "出来事の自然言語値は日本語で、プロトコル値は正規の英語で書くこと。",
    },
})

save("cards/authoring.json", {
    "create_character_brief": "物語に登場させる人物を日本語で説明してください。",
    "create_persona_brief": "あなたが演じる人物を日本語で説明してください。",
})

# Preserve reviewed Japanese prompt translations across regeneration. English
# remains the structural reference and the loader rejects any missing leaf.
ja_prompts = JA / "cards" / "system_prompts.json"
save("cards/system_prompts.json", (
    json.loads(ja_prompts.read_text(encoding="utf-8"))
    if ja_prompts.exists() else load("cards/system_prompts.json")))

comp = load("cards/compositor.json")
comp.update({
    "label_dangling": ["は", "が", "を", "に", "へ", "で", "と", "の", "も", "から", "まで", "より"],
    "articles": [],
    "tone_behavior_words": ["笑み", "微笑", "にやり", "表情", "視線", "仕草"],
    "indefinite_article": {"vowels": "", "vowel": "", "other": ""},
    "linking_participles": [],
    "ordinal_words": {str(i): f"{i}番目" for i in range(2, 13)},
    "second_to_first": [
        ["あなた自身", "私自身"], ["あなたの", "私の"], ["あなた", "私"],
    ],
    "generic_labels": ["声", "見知らぬ人物", "ぼんやりした人影", "あなた", ""],
    "dim_figure": "ぼんやりした人影",
    "dim_figures": "いくつかのぼんやりした人影",
    "count_names": {"1": "一人", "2": "二人", "3": "三人", "4": "四人", "5": "五人",
                    "6": "六人", "7": "七人", "8": "八人", "9": "九人", "10": "十人"},
    "count_words": {"2": "二人", "3": "三人", "4": "四人", "5": "五人",
                    "6": "六人", "7": "七人", "8": "八人", "9": "九人"},
    "tier_phrases": {"within_reach": "手の届く距離", "near": "すぐ近く",
                     "across": "部屋の向こう", "default": "ここ"},
    "leading_connectives": ["そして", "また", "さらに"],
    "pose_prepositions": ["上", "中", "下", "そば", "後ろ", "前", "間", "内側"],
    "join": {"two": "{first}と{last}", "many": "、そして{last}"},
    "dialogue_verbs": {
        "shout": ["叫ぶ", "叫ぶ"],
        "whisper": ["小声で言う", "小声で言う"],
        "mutter": ["つぶやく", "つぶやく"],
        "default": ["言う", "言う"],
    },
    "articulation": {
        "slurred": "。舌が塞がれ、言葉はもつれている",
        "stifled": "。声は塞がれ、ほとんど形にならない",
        "default": "",
    },
    "residue": {
        "lead": {"unconscious": "闇。", "sedated": "濃く漂う闇。",
                 "asleep": "意識は眠りの底にある。", "default": "闇。"},
        "pain": "遠く、感覚の薄い身体に鈍い痛みがある",
        "targeted": "何かに動かされ、方向も分からないまま世界が傾く",
        "loud_event": "巨大で言葉にならない音が沈んだ意識まで届き、消える",
        "closing": {"unconscious": "何も届かない。", "sedated": "何も形を保てない。",
                    "asleep": "", "default": ""},
        "separator": "、",
    },
})
comp["templates"].update({
    "side": " あなたの{side}側",
    "body_part_where_sides": "{whose}の{at}の両側に",
    "body_part_where_side": "{whose}の{at}の{aspect}側から",
    "body_part_where_aspect": "{whose}の{at}の{aspect}から",
    "body_part_tucked": "、現在は衣服の下に隠れている",
    "pose_self_present": "あなたは",
    "pose_self_past": "私は",
    "pose_other_present": "{label}は",
    "pose_other_past": "{label}は",
    "pose_support": "{support}の上に",
    "pose_relation": "{other}に接して",
    "room": "あなたは{room}にいる。",
    "light_dim": "照明は薄暗い。",
    "light_dark": "ここは暗い。",
    "appearance": "{description}が見える。",
    "posture": "あなたは{value}。",
    "activity": "あなたは{value}。",
    "held": "手にしているもの：{items}。",
    "exposed_self": "露出しているあなたの{place}",
    "exposed_other": "露出している{label}の{place}",
    "exposed_detail": "{subject}が見えている：{detail}",
    "exposed_detail_plural": "{subject}が見えている：{detail}",
    "muffled": "くぐもった声：{fragment}",
    "muffled_indistinct": "……何か聞き取れない……",
    "residue_content": "{lead}{body}。",
    "tone_behavior": "{tone}を浮かべ、",
    "tone_noun": "{tone}を声ににじませ、",
    "tone_article": "{tone}声で",
    "tone_adjective": "{tone}声で",
    "dialogue_conducted": "{label}の声が周囲すべてを伝わり、低く間近に響く。「{body}」",
    "dialogue_visible": "{label}は{manner}{articulation}{verb}。「{body}」",
    "dialogue_unseen": "{label}が{articulation}{verb}のが聞こえる。「{body}」",
    "observable_empty": "{label}。",
    "observable": "{label}は{body}。",
    "unknown_actor": "見知らぬ{description}",
    "unknown_actor_fallback": "見知らぬ人物",
    "environment_here": "{label}がここにいる。",
    "environment_nearby": "近くに{label}が見える。",
    "fallback_speech": "{label}：「{quote}」",
    "narrator_immediate": "すぐ周囲の様子が目に入る。",
    "narrator_nothing": "この瞬間、特に何も感じ取れない。",
    "loop_speech": "{label}：「{body}」",
    "loop_faint_sound": "{where}からかすかな音がするが、内容までは聞き取れない。",
    "loop_muffled": "{label}の方から、くぐもった断片が聞こえる。「……{fragment}……」",
    "loop_self_said": "あなたはこう言った。「{quote}」",
    "loop_self_did": "あなたは{surface}",
    "arrived": "{label}が入ってくる。",
    "departed": "{label}が立ち去る。",
    "episode_muffled": "くぐもった声を聞いた：{fragment}",
    "episode_conducted": "{label}の声が周囲を伝わって聞こえた。「{body}」",
    "episode_speech": "{label}の言葉を聞いた。「{body}」",
    "episode_act": "{label}が{action}のを見た",
    "episode_arrived": "{label}が入ってきた。",
    "episode_departed": "{label}が立ち去った。",
    "episode_room": "私は{room}にいた。",
    "episode_appearance": "{description}が見えた。",
    # Adapter-only templates; English does not need these because its native
    # renderer composes the same concepts directly.
    "presence": "{label}がいる。",
    "episode_presence": "{label}がいた。",
    "speech": "{label}：「{body}」",
    "conducted": "{label}の声が周囲を伝わって響く。「{body}」",
    "act": "{label}は{action}",
    "pose": "{label}は{detail}。",
    "episode_pose": "{label}は{detail}だった。",
    "body_region": "{label}の身体：{detail}",
    "episode_body_region": "{label}の身体について{detail}が見えた。",
    "body_state": "{label}の状態：{detail}",
    "episode_body_state": "{label}は{detail}だった。",
})
save("cards/compositor.json", comp)

# LOAD-BEARING: read from EN, never from JA. The `add()` helper below appends
# Japanese alternatives to each pattern, so re-reading the existing Japanese
# card would compound them on every run -- `(?:(?:(?:en|jp)|jp)|jp)`. The two
# surfaces above (compositor, ui.json) deliberately read the EXISTING Japanese
# instead, which is why this one looks inconsistent and must stay that way.
ling = load("cards/linguistics.json")


def add(module, name, *items):
    value = ling[module][name]
    if isinstance(value, dict) and value.get("$type") in ("tuple", "set", "frozenset"):
        value["items"].extend(item for item in items if item not in value["items"])
    else:
        raise TypeError((module, name))


def regex(module, name, japanese):
    value = ling[module][name]
    value["pattern"] = "(?:" + value["pattern"] + "|" + japanese + ")"


common = "agents.common"
add(common, "_REACTIVE_VERBS", "攻撃", "刺す", "撃つ", "掴む", "拘束", "押す", "投げる", "突進", "盗む", "殴る", "斬る")
add(common, "_MENTAL_VERBS", "思う", "考える", "思い出す", "決める", "気づく", "理解する", "知る", "信じる", "疑う", "望む", "恐れる")
add(common, "_AUTONOMY_VERBS", "同意する", "従う", "屈する", "降参する", "落ち着く", "慌てる", "気絶する", "信頼する", "許す", "楽しむ")
add(common, "_AUTONOMY_PHRASES", "身を委ねる", "我慢できない", "抵抗できない", "気が変わる", "恋に落ちる", "理性を失う")
add(common, "_OVERLAP_STOPWORDS", "は", "が", "を", "に", "へ", "で", "と", "の", "も", "から", "まで", "そして", "しかし")
regex(common, "_QUOTED_SPAN_RE", "「[^」]+」|『[^』]+』")
regex(common, "_SPEECH_NARRATION_RE", "言(?:う|った|って)|話す|答える|尋ねる|囁く|ささやく|つぶやく|叫ぶ")
ling[common]["_PLAYER_ACT_VERBS"] += "|取る|掴む|持つ|上げる|下げる|飲む|食べる|歩く|走る|開ける|閉める|見る"
regex(common, "_SUBJECT_PRONOUN_RE", "^(?:彼|彼女|あの人|その人|彼ら)")
ling[common]["_ATTRIBUTION_VERBS"] += "|言う|話す|答える|尋ねる|囁く|つぶやく|叫ぶ"
ling[common]["_LOCOMOTION_VERBS"] += "|歩く|進む|近づく|下がる|走る|渡る|移動する"
add(common, "_INTERIOR_VERBS", "思う", "考える", "知る", "信じる", "疑う", "望む", "恐れる", "決める", "気づく")
ling[common]["_MANIPULATION_VERBS"] += "|掴む|取る|持つ|引く|押す|上げる|開ける|閉める"
add(common, "_OWN_BODY_NOUNS", "身体", "手", "腕", "足", "脚", "顔", "目", "口", "胸", "背中", "腰", "息", "心臓", "肌")
regex(common, "_QUOTE_SPAN_RE", "(「)([^」]{2,})(」)|(『)([^』]{2,})(』)")
regex(common, "_QUOTE_BODY_RE", "「([^」]{2,})」|『([^』]{2,})』")
add(common, "_TONE_NOUNS", "優しさ", "怒り", "不安", "皮肉", "喜び", "疑い", "緊張", "愛情", "悪意")
add(common, "_OBSERVED_STOPWORDS", "は", "が", "を", "に", "へ", "で", "と", "の", "も", "から", "まで")
add(common, "_GENERIC_LABEL_HEADS", "人物", "人影", "声", "姿", "大人", "子供", "誰か")
ling[common]["_YOU_AGREEMENT"].update({})
ling[common]["_APPEARANCE_LABELS"]["items"].extend([
    {"$type": "tuple", "items": ["; wearing:", "、服装は"]},
    {"$type": "tuple", "items": ["; clothing state:", "、衣服の状態は"]},
    {"$type": "tuple", "items": ["; currently:", "、現在は"]},
])
# The ONE speech vocabulary: both dangling-speech healers are built from this
# key, so the inflected forms narration actually uses have to be here and not
# only the dictionary form. `_DANGLING_SPEECH.verb`/`.colon` carry the SHAPE of
# each wound and are seeded whole below, because the Japanese wound is a
# different shape -- the quotative particle stranded before a clause-final verb.
ling[common]["_SPEECH_CUE"] += (
    "|言う|言った|言って|話す|話した|答える|答えた|尋ねる|尋ねた|囁く|囁いた"
    "|ささやく|ささやいた|つぶやく|つぶやいた|叫ぶ|叫んだ"
    "|続ける|続けた|付け加える|付け加えた|返す|返した")
ling[common]["_DANGLING_SPEECH"] = {
    "verb": {
        "pattern": ("(?:と|って)?(?<!そう)({cue})[^\\S\\n]*"
                    "(?:(?P<end>[。！？.!?])|(?P<cont>、)|(?P<eol>$))"),
        "flags": 42,
    },
    "colon": {
        "pattern": ("([^。！？：:\\n]*(?:{cue})[^\\S\\n]*)[：:]"
                    "\\s*[。.]?\\s*(?=\\S|$)"),
        "flags": 34,
    },
    "heal_end": "そう{verb}{end}",
    "heal_cont": "そう{verb}、",
    "heal_stop": "そう{verb}。",
    "heal_colon": "{lead}。",
}
regex(common, "_DIALOGUE_CUE_RE", "言(?:う|った|って)|話す|答える|尋ねる|囁く|ささやく|つぶやく|叫ぶ")
regex(common, "_NPC_PRONOUN_RE", "彼女|彼|彼ら|あの人|その人")
regex(common, "_VIEW_QUOTED_SPAN_RE", "「[^」]*」|『[^』]*』")
# ONE capture group across every pair, so a caller reading group(1) by position
# is right whichever pair matched. Character classes, not alternation, for that
# reason -- `project_check` holds a pack to English's group count.
ling[common]["_VIEW_QUOTE_BODY_RE"]["pattern"] = "[\"“「『]([^\"“”」』]{1,})[\"”」』]"
ling[common]["_QUOTE_PAIRS"]["items"].extend([
    {"$type": "tuple", "items": ["「", "」"]},
    {"$type": "tuple", "items": ["『", "』"]},
])
add(common, "_QUOTE_CHARS", "「", "」", "『", "』")
regex(common, "_NARRATION_QUOTE_RE", "「[^」]*」|『[^』]*』")
regex(common, "_NARRATION_DOUBLED_QUOTE_RE", "「{2,}|『{2,}")
regex(common, "_NARRATION_DANGLING_QUOTE_RE", "「[^」]*$|『[^』]*$")
regex(common, "_FIRST_PERSON_RE", "私|わたし|僕|ぼく|俺|おれ|自分|我々|わたしたち|僕たち|俺たち")
regex(common, "_SECOND_PERSON_RE", "あなた|君|きみ|お前|貴方|あんた")
# Narration tense (agents/common.py `_check_narration_tense_match`).
# Japanese fixes tense at the CLAUSE END rather than in a separate
# auxiliary, so the cues are endings: the た-family is past, plain
# u-row/です/ます is present. Deliberately not scored on だ alone, which is
# the present copula whose past is だった -- the shared character is the
# one place a naive ending scan inverts. Unmeasured against a Japanese
# corpus; the check it feeds is warning-only for exactly this reason.
regex(common, "_PAST_TENSE_RE",
      "(?:った|いた|えた|した|きた|んだ|めた|ちた|べた|げた|ねた|"
      "だった|でした|ました|かった|なかった)(?=[。、」』\\s]|$)")
regex(common, "_PRESENT_TENSE_RE",
      "(?:ます|ません|です|である|[るうくすつぬぶむぐ]|だ)"
      "(?=[。、」』\\s]|$)")
add(common, "_THIRD_SUBJECT_PRONOUNS", "彼", "彼女", "彼ら")
ling[common]["_PRONOUN_GROUPS"].update({
    "彼": {"$type": "tuple", "items": ["彼", "彼の", "彼自身"]},
    "彼女": {"$type": "tuple", "items": ["彼女", "彼女の", "彼女自身"]},
    "彼ら": {"$type": "tuple", "items": ["彼ら", "彼らの", "彼ら自身"]},
})
regex(common, "_LOOK_VERB_RE", "見る|見つめる|眺める|目を向ける|視線を向ける|指さす|振り向く")
add(common, "_SUBJECT_LEADS", "私", "僕", "俺", "あなた", "君", "彼", "彼女", "彼ら", "その", "この", "あの")
regex(common, "_CLAUSE_BREAKS", "そして|しかし|だが|ので|から|ながら|とき|前に|後で|まで|、|；|：")
add(common, "ATTEMPT_CUES", "しようとする", "試みる", "狙う", "手を伸ばす", "近づこうとする")
add(common, "_BREATH_CONJUNCTIONS", "そして", "しかし", "または", "ので", "から", "ながら", "とき", "まで")
add(common, "_NAME_TITLE_TOKENS", "博士", "先生", "隊長", "司令官", "大尉", "中尉", "軍曹", "殿", "様", "さん")
add(common, "_NAME_LEADERS", "博士", "先生", "隊長", "司令官", "大尉", "中尉", "軍曹")
regex(common, "_NEW_SUBJECT_RE", "^(?:私|僕|俺|あなた|君|彼|彼女|彼ら|それ|これ|あれ)")
regex(common, "_PROXIMITY_RE", "近づく|一歩近づく|距離を詰める|手の届く距離|一歩下がる|離れる")
add(common, "_DEFINITE_DETS", "この", "その", "あの", "私の", "あなたの", "彼の", "彼女の")
add(common, "_DIRECTOR_VOICEABLE_KINDS", "生物", "動物", "怪物", "ゴーレム", "自動人形", "ゾンビ", "ドローン", "群れ")
add(common, "_CONFLICT_VERBS", "攻撃", "掴む", "拘束", "盗む", "壊す", "破る", "押し入る", "撃つ", "刺す", "殴る", "斬る", "入る", "出る", "立ち去る")
add(common, "_LEADING_SUBJECT_PRONOUNS", "彼", "彼女", "彼ら", "それ")
add(common, "_GENERIC_ROOM_WORDS", "部屋", "場所", "ここ", "区画")
add(common, "_PARTIAL_QUOTE_PREFIXES", "何か", "……何か")
ling[common]["_VISUAL_CONTRADICTION_RES"]["items"].extend([
    {"$type": "regex", "pattern": "話し手の姿は見えない", "flags": 34},
    {"$type": "regex", "pattern": "はっきりした人影は見えない", "flags": 34},
    {"$type": "regex", "pattern": "(?:相手|話し手|誰)の?姿は見えない", "flags": 34},
    {"$type": "regex", "pattern": "(?:相手|話し手|誰も)を?見ることはできない", "flags": 34},
])
# Japanese marks place with a POSTPOSITION, so the room name leads the phrase
# instead of trailing it. Same question, mirrored shape -- which is why the
# pack holds the whole phrase with a {room} slot rather than a preposition list.
ling[common]["_PLACEMENT_PHRASE"]["pattern"] = (
    "(?:" + ling[common]["_PLACEMENT_PHRASE"]["pattern"]
    + "|{room}(?:の(?:中|なか|奥))?(?:に|で|へ|にて))")
portal = ling[common]["_PORTAL_STATE"]
# Inside the group, not beside it: appending after the closing paren would
# make the Japanese branch escape the alternation the caller splices in.
portal["open"] = portal["open"][:-1] + "|開いて|開いた|開け放たれ|開け放た)"
portal["shut"] = portal["shut"][:-1] + "|閉じ|閉ま|閉ざされ|施錠され)"
portal["modifier"] = "(?:" + portal["modifier"] + "|{state}(?:た|ている)?{name})"
portal["predicate"] = ("(?:" + portal["predicate"]
                       + "|{name}[^。！？\\n、；]{0,60}?{state})")
portal["join"] = "\\s*"
add(common, "_INTERIOR_STATES", "恐怖", "不安", "絶望", "喜び", "欲望", "怒り", "悲しみ", "動揺")
add(common, "_INTERIOR_CERTAINTY", "本当", "明らか", "確か", "紛れもない", "はっきり")
regex(common, "_CLAUSE_SPLIT", "、|。|；|：|そして|しかし|だが|ので|から|ながら|とき")
regex(common, "_NARR_LOWERING", "下げる|降ろす|下がる|沈む")
regex(common, "_NARR_RAISING", "上げる|持ち上げる|昇る")

director = "agents.director"
add(director, "_DECL_STOPWORDS", "は", "が", "を", "に", "へ", "で", "と", "の", "も", "そして", "しかし")
regex(director, "_QUOTED_UNIT_RE", "「([^」]{2,})」|『([^』]{2,})』")
add(director, "_RESTRAINT_KEYWORDS", "押さえつけ", "拘束", "人質", "銃を向け", "首を絞め", "掴まれ")
ling[director]["_FAINT_VERB"] += "|気絶する|気を失う|失神する"
regex(director, "_UNCONSCIOUSNESS_CUE", "意識を失う|気絶|失神|昏倒|意識がない|気を失った")
regex(director, "_SLEEP_CUE", "眠る|眠っている|寝る|寝ている|眠りにつく|まどろむ")
regex(director, "_ROUSE_CUE", "目を覚ます|起きる|起こす|揺さぶる|呼び起こす")
regex(director, "_STAY_UNDER_CUE", "眠ったまま|眠り続ける|意識が戻らない|気絶したまま")
ling[director]["_DESTRUCTION_TERMINAL_CUES"] += "|(?:完全に)?(?:破壊された|崩壊した|焼失した|消滅した|瓦礫になった)"
ling[director]["_DESTRUCTION_VERB_OBJECT"] += "|破壊する|焼き払う|崩壊させる|消滅させる"
ling[director]["_DESTRUCTION_OF_PHRASE"] += "|残骸|灰|瓦礫|焼け跡"
add(director, "_RAPID_FOLLOW_VERBS", "走る", "駆ける", "逃げる", "突進する", "疾走する")
regex(director, "_CLAUSE_SPLIT_RE", "。|！|？|、(?:そして|しかし|だが)|そして|それから")
add(director, "_TITLE_ABBREV", "博士", "先生", "隊長", "司令官", "大尉", "中尉")
ling[director]["_OMISSION_CATEGORY_ALIASES"].update({
    "部屋": "rooms", "場所": "rooms", "扉": "adjacency", "通路": "adjacency",
    "位置": "positions", "移動": "positions", "姿勢": "poses", "服装": "attire",
    "状態": "conditions", "会話": "dialogue", "所持品": "inventory",
})

regex("agents.character", "_REFRAIN_WORD_RE", "[一-龯々ぁ-んァ-ヶー]{1,}")
verdicts = ling["agents.character"]["_VERDICTS"]["items"]
translations = [
    "ここから見える限り先へ進む道はない", "中に入ったが何度も引き返すしかなかった",
    "その先の扉はすべて通ったことがある", "同じいくつかの部屋を回り続けている",
    "この出入口を通ったことはない", "以前この道で目的地に着けた", "以前ここを通ったことがある",
]
for row, text in zip(verdicts, translations):
    row["items"][2] = text
# `unentered` is the one verdict the code mints rather than reading from the
# table, so it needs its own row here or a Japanese story receives a Japanese
# verdict with an English sentence welded on. Same for the clauses that ride on
# top of any verdict.
ling["agents.character"]["_VERDICT_TEMPLATE"] = "{label}——{detail}"
ling["agents.character"]["_VERDICT_UNENTERED"]["items"] = [
    "未踏",
    ("他に出口はないが、まだ中に入ったことがない。部屋の中に何があるかは、"
     "その先に何があるかとは別の問題であり、たどり着く価値のあるものは"
     "たいてい通り道ではない"),
]
ling["agents.character"]["_VERDICT_DETAILS"].update({
    "entered_recently": "直近の十数歩でそこに{count}回入っている",
    "frontier_adjacent": "。その先の部屋には、まだ通ったことのない扉がある",
    "frontier_distant":
        "。まだ通ったことのない最も近い扉は、その方向におよそ{hops}部屋先にある",
})

ling["agents.narration"]["_CRAFT_TELLS"].extend([
    {"$type": "tuple", "items": ["小さく息を吐(?:く|いた)", "小さく息を吐く"]},
    {"$type": "tuple", "items": ["目を細め(?:る|た)", "目を細める"]},
    {"$type": "tuple", "items": ["わずかに首を傾げ(?:る|た)", "わずかに首を傾げる"]},
])
add("agents.composer", "_SUDDEN_VERBS", "掴む", "飛びかかる", "叩きつける", "叫ぶ", "突進する", "倒れる", "投げる", "撃つ", "砕ける")
save("cards/linguistics.json", ling)

english_ui = load("ui.json")
ja_ui_path = JA / "ui.json"
existing_ui = (json.loads(ja_ui_path.read_text(encoding="utf-8"))
               if ja_ui_path.exists() else {})
ui = {key: existing_ui.get(key, value) for key, value in english_ui.items()}
translations = {
    "language.name": "日本語",
    "Stories": "物語", "Characters": "キャラクター", "Personas": "ペルソナ",
    "Lorebooks": "ロアブック", "Settings": "設定", "Prompts": "プロンプト",
    "Create": "作成", "Create story": "物語を作成", "New story": "新しい物語",
    "New entry": "新しい項目", "New lorebook": "新しいロアブック",
    "Save": "保存", "Saved.": "保存しました。", "Saving…": "保存中…",
    "Cancel": "キャンセル", "Close": "閉じる", "Delete": "削除", "Remove": "削除",
    "Edit narration": "語りを編集", "Edit player input:": "プレイヤー入力を編集：",
    "Name": "名前", "Title": "タイトル", "Summary": "概要", "Details": "詳細",
    "Description": "説明", "Appearance": "外見", "Abilities": "能力", "Aliases": "別名",
    "Scenario?": "シナリオは？", "Story name": "物語の名前", "Current story": "現在の物語",
    "Story input": "物語への入力", "Your action or speech": "行動または台詞",
    "Act, speak, or leave empty…": "行動や台詞を入力（空欄でも可）…",
    "Send": "送信", "Send ➤": "送信 ➤", "Stop": "停止", "■ Stop": "■ 停止",
    "Working…": "処理中…", "Loading…": "読み込み中…", "Generating": "生成中",
    "Generate": "生成", "✨ Generate": "✨ 生成", "Import": "インポート",
    "Export": "エクスポート", "⤓ Import": "⤓ インポート", "⤓ Export": "⤓ エクスポート",
    "Next →": "次へ →", "← Back": "← 戻る", "Done": "完了", "Selected": "選択済み",
    "Language": "言語", "Story language": "物語の言語", "Interface language": "画面の言語",
    "Theme": "テーマ", "Themes": "テーマ", "Use theme": "このテーマを使う",
    "Story text size": "本文の文字サイズ", "Compact": "コンパクト", "Comfortable": "標準",
    "Large": "大", "Extra large": "特大", "API connections": "API接続",
    "Connect": "接続", "Provider": "プロバイダー", "Providers": "プロバイダー",
    "API key": "APIキー", "Fetch models": "モデルを取得", "Model": "モデル",
    "Agent models saved.": "エージェントモデルを保存しました。",
    "Sign in": "サインイン", "Username": "ユーザー名", "Password": "パスワード",
    "Confirm password": "パスワードを確認", "Create account": "アカウントを作成",
    "Host access": "ホストアクセス", "Unauthorized": "認証されていません",
    "Join story": "物語に参加", "Join code": "参加コード",
    "Join a friend's story": "友達の物語に参加", "Enter": "入る",
    "Enter the join code your friend gave you.": "友達から受け取った参加コードを入力してください。",
    "Sonder Engine — Join a Story": "Sonder Engine — 物語に参加",
    "Sonder Engine — Sign In": "Sonder Engine — サインイン",
    "Create your host account": "ホストアカウントを作成",
    "Step 1 of 3 — your persona": "ステップ1/3 — あなたのペルソナ",
    "Step 3 of 3 — the scenario": "ステップ3/3 — シナリオ",
    "Two steps and you're writing.": "あと2ステップで物語を始められます。",
    "Ready when you are.": "準備ができたら始めましょう。",
    "Select or create a story to begin.": "物語を選ぶか、新しく作成してください。",
    "No story selected": "物語が選択されていません", "No lorebooks yet.": "ロアブックはまだありません。",
    "No relationships yet.": "関係はまだありません。", "No file selected": "ファイルが選択されていません",
    "Search lorebook tree": "ロアブックを検索", "Filter entries…": "項目を絞り込み…",
    "Filter lorebooks:": "ロアブックを絞り込み：", "Search": "検索",
    "Category": "カテゴリ", "Type": "種類", "Content": "内容", "Notes": "メモ",
    "Keys": "キー", "Importance": "重要度", "Relationship": "関係",
    "Background presences": "背景の登場人物", "Dialogue configuration": "会話設定",
    "Appearance and themes": "外観とテーマ", "Background work": "バックグラウンド処理",
    "Cast, persona and lorebooks": "登場人物・ペルソナ・ロアブック",
    "Genre and style": "ジャンルと文体", "Lore": "ロア",
    "Story tools": "物語ツール", "technical detail": "技術的な詳細",
    "Room ambience": "部屋の環境音", "Scene backdrops": "場面の背景画像",
    "Ambience volume": "環境音の音量", "Mute ambience": "環境音をミュート",
    "Different sound for this room": "この部屋には別の音を使う",
    "Chime when a turn or a generation finishes": "ターンや生成の完了時に音を鳴らす",
    "Act, speak, or leave empty to establish the scene… (Ctrl+Enter to send)":
        "行動や台詞を入力。空欄なら場面を開始…（Ctrl+Enterで送信）",
    "Shows a detailed technical log of every internal stage as a turn runs, including raw model output. Off by default for a cleaner view — the story plays out exactly the same either way.":
        "ターン中の各内部段階とモデルの生出力を詳しく表示します。通常は見やすさのためオフですが、物語の進行はどちらでも同じです。",
    "World state": "世界の状態", "World state saved.": "世界の状態を保存しました。",
    "Who's where": "人物の居場所", "Frames": "時間軸", "New frame:": "新しい時間軸：",
    "Check for updates": "更新を確認", "Software updates": "ソフトウェア更新",
    "Something went wrong": "エラーが発生しました", "Try again": "もう一度試す",
    "Close dialog": "ダイアログを閉じる", "Toggle sidebar": "サイドバーを切り替える",
    "Advanced generator →": "詳細ジェネレーター →", "Find and fill gaps": "不足を検出して補完",
    "AI reinterpretation": "AIで再解釈", "✨ Reinterpret": "✨ 再解釈",
    "Promote": "昇格", "✨ Promote to character": "✨ キャラクターに昇格",
    "Private history": "非公開の経歴", "History & Voice": "経歴と話し方",
    "Embodiment (Visible & Senses)": "身体（外見と感覚）", "Attire": "服装",
    "Injury": "負傷", "Stamina": "スタミナ", "Satiation": "満足度",
    "NSFW: OFF": "成人向け：オフ", "OFF": "オフ", "ON": "オン", "Off": "オフ",
    "Accept all": "すべて承認", "Reject all": "すべて却下",
    "Apply accepted operations": "承認した操作を適用", "Applying…": "適用中…",
    "Written by": "作成者", "Seen by": "認識者", "Decided by": "決定者",
    "Setting the scene": "場面を設定中", "Checking the surroundings": "周囲を確認中",
    "Characters reacting": "キャラクターが反応中", "Characters responding": "キャラクターが応答中",
    "Deciding what happens": "結果を決定中", "Writing the scene": "場面を執筆中",
}
# Line 317 above deliberately PRESERVES whatever Japanese is already on disk,
# and this loop used to overwrite it twenty lines later -- two opposite
# conventions in one function. The seed values here are a starting point for a
# key that has never been translated; a value already in the pack is the
# reviewed one and wins. Measured: 74 curated translations were silently
# reverted on every run, including 「背景の仕事」 replacing the correct reading
# of "Background work".
for source, translated in translations.items():
    if source in ui and ui[source] == english_ui.get(source):
        ui[source] = translated
save("ui.json", ui)
