import re
from dataclasses import dataclass


UNKNOWN_HARDNESS = "unknown"

HARDNESS_PRIORITY = {
    "role_reversal": 0,
    "wrong_action": 1,
    "wrong_victim": 2,
    "wrong_aggressor": 3,
    "bystander_substitution": 4,
    "wrong_location": 5,
    "wrong_category": 6,
    "none_claim": 7,
    "other_in_cast": 8,
    "cross_video": 9,

    # --hardness-profile=frequency_inverted mode. Rank lowest because they


    "frequency_saturation": 10,
}

HARDNESS_CATEGORIES = tuple(HARDNESS_PRIORITY.keys())


@dataclass(frozen=True)
class HardnessRecipe:
    counts: dict[str, int]


    mode: str = "standard"

    def total(self) -> int:
        return sum(self.counts.values())

    def expand(self) -> list[str]:

        out: list[str] = []
        for cat, n in self.counts.items():
            out.extend([cat] * n)
        return out


# qtype because options are drawn from the fixed 4-label vocabulary.

# Slot choice rationale per qtype:


DEFAULT_RECIPES: dict[str, HardnessRecipe] = {

    "aggressor_identification": HardnessRecipe(
        {"role_reversal": 1, "bystander_substitution": 2, "cross_video": 4}
    ),
    "victim_recognition": HardnessRecipe(
        {"role_reversal": 1, "bystander_substitution": 2, "cross_video": 4}
    ),
    "perspective_aggressor": HardnessRecipe(
        {"role_reversal": 1, "bystander_substitution": 2, "cross_video": 4}
    ),
    "bystander_detection": HardnessRecipe(
        {"wrong_aggressor": 2, "wrong_victim": 2, "cross_video": 3}
    ),


    "primary_action": HardnessRecipe({"wrong_category": 7}),
    "social_appropriateness": HardnessRecipe({"wrong_category": 7}),


    "scene_location": HardnessRecipe({"wrong_category": 7}),


    "compound_aggressor_action_victim": HardnessRecipe(
        {"role_reversal": 1, "wrong_action": 1, "wrong_victim": 1,
         "wrong_aggressor": 1, "bystander_substitution": 1, "cross_video": 2}
    ),
    "interaction_summary": HardnessRecipe(
        {"role_reversal": 1, "wrong_action": 1, "wrong_victim": 1,
         "wrong_aggressor": 1, "bystander_substitution": 1, "cross_video": 2}
    ),
    "sequence_verification": HardnessRecipe(
        {"role_reversal": 1, "wrong_action": 1, "wrong_victim": 1,
         "wrong_aggressor": 1, "bystander_substitution": 1, "cross_video": 2}
    ),


    "compound_action_victims": HardnessRecipe(
        {"role_reversal": 1, "wrong_action": 2, "wrong_victim": 2,
         "bystander_substitution": 1, "cross_video": 1}
    ),

    "compound_action_aggressor": HardnessRecipe(
        {"role_reversal": 1, "wrong_action": 2, "wrong_aggressor": 2,
         "bystander_substitution": 1, "cross_video": 1}
    ),

    "compound_aggressor_victim": HardnessRecipe(
        {"role_reversal": 1, "wrong_victim": 2, "wrong_aggressor": 2,
         "bystander_substitution": 1, "cross_video": 1}
    ),

    # don't vary the text. Keep the budget on action + location + cross.
    "compound_action_location": HardnessRecipe(
        {"wrong_action": 3, "wrong_location": 3, "cross_video": 1}
    ),
    # aggressor + location: wrong_victim/wrong_action don't change the render.
    "compound_aggressor_location": HardnessRecipe(
        {"role_reversal": 1, "wrong_aggressor": 2, "bystander_substitution": 1,
         "wrong_location": 2, "cross_video": 1}
    ),

    "compound_bystander_location": HardnessRecipe(
        {"bystander_substitution": 2, "wrong_location": 3, "cross_video": 2}
    ),


    "role_identification": HardnessRecipe(
        {"role_reversal": 1, "bystander_substitution": 1, "none_claim": 1}
    ),
}


def TRICK_RECIPE_FACTORY(num_distractors: int) -> "HardnessRecipe":
    return HardnessRecipe({"cross_video": num_distractors})


FREQUENCY_INVERTED_SUPPORTED_QTYPES = frozenset({
    "compound_aggressor_action_victim",
    "interaction_summary",
    "sequence_verification",
})


def _inverted_recipe(num_distractors: int = 7) -> "HardnessRecipe":
    return HardnessRecipe(
        counts={"role_reversal": 1, "frequency_saturation": num_distractors - 1},
        mode="frequency_inverted",
    )


FREQUENCY_INVERTED_RECIPES: dict[str, "HardnessRecipe"] = {
    qtype: _inverted_recipe() for qtype in FREQUENCY_INVERTED_SUPPORTED_QTYPES
}


def apply_hardness_profile(
    recipes: dict[str, "HardnessRecipe"], profile: str
) -> dict[str, "HardnessRecipe"]:

    if profile == "balanced" or profile == "custom":
        return dict(recipes)
    if profile == "easy":
        return {
            qtype: HardnessRecipe({"cross_video": r.total()})
            for qtype, r in recipes.items()
        }
    if profile == "hard":
        out: dict[str, HardnessRecipe] = {}
        for qtype, r in recipes.items():
            counts = dict(r.counts)
            cv = counts.pop("cross_video", 0)
            if cv > 0:
                if "role_reversal" in counts:
                    counts["role_reversal"] += cv
                elif "wrong_action" in counts:
                    counts["wrong_action"] += cv
                elif "wrong_category" in counts:
                    counts["wrong_category"] += cv
                else:


                    counts["cross_video"] = cv
            out[qtype] = HardnessRecipe(counts)
        return out
    if profile == "frequency_inverted":


        out = apply_hardness_profile(recipes, "hard")
        for qtype in FREQUENCY_INVERTED_RECIPES:
            base_total = recipes[qtype].total() if qtype in recipes else 7
            out[qtype] = _inverted_recipe(base_total)
        return out
    raise ValueError(f"Unknown hardness profile: {profile!r}")


PROFILE_RECIPES = {


    "easy":                lambda recipes=None: apply_hardness_profile(recipes or DEFAULT_RECIPES, "easy"),
    "balanced":            lambda recipes=None: apply_hardness_profile(recipes or DEFAULT_RECIPES, "balanced"),
    "hard":                lambda recipes=None: apply_hardness_profile(recipes or DEFAULT_RECIPES, "hard"),
    "custom":              lambda recipes=None: apply_hardness_profile(recipes or DEFAULT_RECIPES, "custom"),
    "frequency_inverted":  lambda recipes=None: apply_hardness_profile(recipes or DEFAULT_RECIPES, "frequency_inverted"),
}


# Question types that do NOT go through the Fake Entry recipe path. Count


# never runs for it.
NON_RECIPE_QTYPES = frozenset({
    "role_count_aggressor",
    "role_count_victim",
    "role_count_bystander",
    "compound_aggressor_victim_count",
    "compound_victim_bystander_count",
})


RE_AAV = re.compile(
    r"^(?P<agg>.+?)\s+performed\s+(?P<act>.+?)\s+on\s+(?P<vic>.+)$", re.I
)
RE_INTERACTION = re.compile(
    r"^(?P<agg>.+?)\s+performs\s+(?:the\s+)?action\s+of\s+(?P<act>.+?)\s+on\s+(?P<vic>.+)$",
    re.I,
)
RE_SEQ = re.compile(
    r"^(?P<agg>.+?),\s*who\s+is\s+the\s+aggressor,\s*performed\s+the\s+action\s+of\s+"
    r"(?P<act>.+?)\s+against\s+(?P<vic>.+)$",
    re.I,
)
RE_AV = re.compile(
    r"^\s*aggressor:\s*(?P<agg>.+?);\s*victim:\s*(?P<vic>.+?)\s*$", re.I
)
RE_ACT_VICTIM = re.compile(r"^\s*(?P<act>[^;]+?);\s*victim:\s*(?P<vic>.+?)\s*$", re.I)
RE_ACT_AGG = re.compile(r"^\s*(?P<act>[^;]+?);\s*aggressor:\s*(?P<agg>.+?)\s*$", re.I)
RE_AGG_LOC = re.compile(
    r"^(?P<agg>.+?)\s+in\s+(?P<loc>.+)$", re.I
)
RE_AGG_LOC_UNCLEAR = re.compile(
    r"^(?P<agg>.+?);\s*location\s+unclear\s*$", re.I
)
RE_SOCIAL = re.compile(
    r"^the\s+action\s+performed\s+by\s+(?P<agg>.+)$", re.I
)


def _parse_by_qtype(qtype: str, text: str) -> tuple[str | None, str | None, str | None, str | None]:

    t = text.strip()
    if qtype == "compound_aggressor_action_victim":
        m = RE_AAV.match(t)
        if m:
            return m["agg"].strip(), m["act"].strip(), m["vic"].strip(), None
    elif qtype == "interaction_summary":
        m = RE_INTERACTION.match(t)
        if m:
            return m["agg"].strip(), m["act"].strip(), m["vic"].strip(), None
    elif qtype == "sequence_verification":
        m = RE_SEQ.match(t)
        if m:
            return m["agg"].strip(), m["act"].strip(), m["vic"].strip(), None
    elif qtype == "compound_aggressor_victim":
        m = RE_AV.match(t)
        if m:
            return m["agg"].strip(), None, m["vic"].strip(), None
    elif qtype == "compound_action_victims":
        m = RE_ACT_VICTIM.match(t)
        if m:
            return None, m["act"].strip(), m["vic"].strip(), None
    elif qtype == "compound_action_aggressor":
        m = RE_ACT_AGG.match(t)
        if m:
            return m["agg"].strip(), m["act"].strip(), None, None
    elif qtype == "compound_aggressor_location":
        m = RE_AGG_LOC_UNCLEAR.match(t)
        if m:
            return m["agg"].strip(), None, None, "unclear"
        m = RE_AGG_LOC.match(t)
        if m:
            return m["agg"].strip(), None, None, m["loc"].strip()
    elif qtype == "compound_bystander_location":
        m = RE_AGG_LOC.match(t)
        if m:

            return None, None, None, m["loc"].strip()
    elif qtype == "social_appropriateness":
        m = RE_SOCIAL.match(t)
        if m:
            return m["agg"].strip(), None, None, None
    return None, None, None, None


_STOP = {
    "a", "an", "the", "is", "of", "and", "with", "on", "in", "at", "for",
    "by", "to", "who", "that", "this", "person", "people", "group",
}


# substitution must refuse to swap onto or from them; otherwise the Fake


_GENERIC_TOKENS = {
    "group", "groups", "bystanders", "others", "many", "several",
    "people", "crowd", "everyone", "anyone", "someone", "none",
    "unknown", "unidentified",
}

_GENERIC_PHRASES = (
    "group of",
    "a group",
    "others",
    "no one",
    "no individual",
    "no person",
    "no people",
    "no bystander",
    "no aggressor",
    "no victim",
    "not shown",
    "not visible",
    "unclear",
    "unknown",
)


def _is_specific(value) -> bool:

    if value is None:
        return False
    if isinstance(value, list):
        survivors = [v for v in value if _is_specific(v)]
        return len(survivors) > 0
    if not isinstance(value, str):
        return False
    s = value.strip().lower()
    if not s:
        return False
    if s in _GENERIC_TOKENS:
        return False
    for phrase in _GENERIC_PHRASES:
        if phrase in s:
            return False
    return True


def _specific_bystanders(entry: dict) -> list[str]:

    value = entry.get("bystanders") or entry.get("bystander")
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if _is_specific(value) else []
    if isinstance(value, list):
        return [v.strip() for v in value if isinstance(v, str) and _is_specific(v)]
    return []


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9']+", (s or "").lower()) if t not in _STOP}


def _slot_match(a: str | None, b: str | None, thresh: float = 0.5) -> bool:
    if not a or not b:
        return False
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / max(1, len(ta | tb)) >= thresh


def _text_mentions(haystack: str, needle: str | None) -> bool:
    if not needle:
        return False
    return _slot_match(haystack, needle)


def _bystander_strings(bystanders) -> list[str]:
    if not bystanders:
        return []
    if isinstance(bystanders, list):
        return [str(b) for b in bystanders if b]
    s = str(bystanders)
    parts = re.split(r"\s+and\s+|,\s*", s)
    return [p.strip() for p in parts if p.strip()]


def _any_bystander_match(slot: str | None, bystanders) -> bool:
    if not slot:
        return False
    return any(_slot_match(slot, b) for b in _bystander_strings(bystanders))


NONE_MARKERS = (
    "no one", "no individual", "no actions performed", "no aggressive action",
    "no bystanders", "none of the above", "not shown", "unclear",
    "no one appears", "no one in the video",
)


def _is_none_claim(d: str) -> bool:
    dl = d.lower()
    return any(marker in dl for marker in NONE_MARKERS)


def classify_distractor(
    qtype: str,
    distractor: str,
    correct_answer: str,
    annotation: dict,
) -> str:
    agg = str(annotation.get("aggressor") or "").strip()
    vic = str(annotation.get("victim") or "").strip()
    act = str(annotation.get("action") or "").strip()
    bys = annotation.get("bystanders") or ""
    env = str(annotation.get("environment") or "").strip()

    d = distractor.strip()
    dl = d.lower()

    if _is_none_claim(d):
        return "none_claim"

    if qtype == "role_identification":
        c = correct_answer.lower().strip()
        if dl == "victim" and c == "aggressor":
            return "role_reversal"
        if dl == "aggressor" and c == "victim":
            return "role_reversal"
        if dl == "bystander":
            return "bystander_substitution"
        return "other_in_cast"

    if qtype == "primary_action":
        return "wrong_category"

    if qtype == "scene_location":
        return "wrong_category"

    if qtype in ("aggressor_identification", "perspective_aggressor"):
        if _slot_match(d, vic):
            return "role_reversal"
        if _any_bystander_match(d, bys):
            return "bystander_substitution"
        if _slot_match(d, agg):
            return "other_in_cast"
        return "cross_video"

    if qtype == "victim_recognition":
        if _slot_match(d, agg):
            return "role_reversal"
        if _any_bystander_match(d, bys):
            return "bystander_substitution"
        if _slot_match(d, vic):
            return "other_in_cast"
        return "cross_video"

    if qtype == "bystander_detection":
        if _slot_match(d, agg) or _slot_match(d, vic):
            return "wrong_aggressor"
        if _any_bystander_match(d, bys):
            return "other_in_cast"
        return "cross_video"

    d_agg, d_act, d_vic, d_loc = _parse_by_qtype(qtype, d)
    c_agg, c_act, c_vic, c_loc = _parse_by_qtype(qtype, correct_answer)

    ref_agg = c_agg or agg
    ref_vic = c_vic or vic
    ref_act = c_act or act
    ref_loc = c_loc or env

    if qtype == "compound_bystander_location":
        if d_loc and ref_loc and not _slot_match(d_loc, ref_loc):
            return "wrong_location"
        return "other_in_cast"

    if qtype == "compound_aggressor_location":
        if d_agg and _slot_match(d_agg, ref_agg):
            if d_loc and ref_loc and not _slot_match(d_loc, ref_loc):
                return "wrong_location"
            return "other_in_cast"
        if _any_bystander_match(d_agg, bys):
            return "bystander_substitution"
        if _slot_match(d_agg, ref_vic):
            return "role_reversal"
        return "cross_video"

    if qtype == "social_appropriateness":
        if _slot_match(d_agg, ref_vic):
            return "role_reversal"
        if _any_bystander_match(d_agg, bys):
            return "bystander_substitution"
        if _slot_match(d_agg, ref_agg):
            return "other_in_cast"
        return "cross_video"

    agg_is_correct_agg = _slot_match(d_agg, ref_agg)
    agg_is_correct_vic = _slot_match(d_agg, ref_vic)
    vic_is_correct_agg = _slot_match(d_vic, ref_agg)
    vic_is_correct_vic = _slot_match(d_vic, ref_vic)
    agg_is_bystander = _any_bystander_match(d_agg, bys)
    vic_is_bystander = _any_bystander_match(d_vic, bys)

    if agg_is_correct_vic and vic_is_correct_agg:
        return "role_reversal"

    if agg_is_correct_agg and vic_is_correct_vic:
        if d_act and ref_act and not _slot_match(d_act, ref_act):
            return "wrong_action"
        return "other_in_cast"

    if agg_is_correct_agg and not vic_is_correct_vic:
        return "bystander_substitution" if vic_is_bystander else "wrong_victim"

    if vic_is_correct_vic and not agg_is_correct_agg:
        return "bystander_substitution" if agg_is_bystander else "wrong_aggressor"

    if agg_is_bystander or vic_is_bystander:
        return "bystander_substitution"

    if agg_is_correct_agg or vic_is_correct_vic or agg_is_correct_vic or vic_is_correct_agg:
        return "other_in_cast"

    return "cross_video"
