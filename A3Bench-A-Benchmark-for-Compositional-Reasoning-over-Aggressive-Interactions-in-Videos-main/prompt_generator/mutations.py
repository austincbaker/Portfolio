import random
from typing import Dict, Any, Callable, Tuple, Set, Optional

from prompt_generator.hardness import (
    HARDNESS_PRIORITY,
    _is_specific,
    _specific_bystanders,
)
from prompt_generator.answer_bank import AnswerBank

def _pick_different_person(
    bank: AnswerBank, exclude_lower: Set[str]
) -> Optional[str]:

    candidates = [p for p in bank.people if p.lower() not in exclude_lower]
    if not candidates:
        return None
    return random.choice(candidates)


def _pick_different_environment(
    bank: AnswerBank, exclude_lower: Set[str]
) -> Optional[str]:
    candidates = [e for e in bank.environments if e.lower() not in exclude_lower]
    if not candidates:
        return None
    return random.choice(candidates)


def _pick_unused_action(
    bank: AnswerBank, used_actions: Set[str], forbid: Optional[str] = None
) -> Optional[str]:

    forbid_lower = forbid.lower() if isinstance(forbid, str) else None
    candidates = [
        a for a in bank.actions
        if a.lower() not in used_actions and (forbid_lower is None or a.lower() != forbid_lower)
    ]
    if not candidates:
        return None
    action = random.choice(candidates)
    used_actions.add(action.lower())
    return action


def _pick_different_annotation(
    all_annotations: list, exclude_key: Optional[str] = None
) -> Optional[dict]:

    if not all_annotations:
        return None
    pool = [
        a for a in all_annotations
        if (a.get("file_name") or a.get("video_name")) != exclude_key
        and _is_specific(a.get("aggressor"))
        and _is_specific(a.get("victim"))
    ]
    if not pool:
        return None
    return random.choice(pool)


def mutate_role_reversal(
    entry: Dict[str, Any], bank: AnswerBank, used_actions: Set[str], **_
) -> Tuple[Optional[Dict[str, Any]], str]:

    if not _is_specific(entry.get("aggressor")) or not _is_specific(entry.get("victim")):
        return None, "role_reversal"
    new_action = _pick_unused_action(bank, used_actions, forbid=entry.get("action"))
    if new_action is None:
        return None, "role_reversal"
    new_entry = entry.copy()
    new_entry["aggressor"] = entry["victim"]
    new_entry["victim"] = entry["aggressor"]
    new_entry["action"] = new_action
    return new_entry, "role_reversal"


def mutate_wrong_action(
    entry: Dict[str, Any], bank: AnswerBank, used_actions: Set[str], **_
) -> Tuple[Optional[Dict[str, Any]], str]:
    new_action = _pick_unused_action(bank, used_actions, forbid=entry.get("action"))
    if new_action is None:
        return None, "wrong_action"
    new_entry = entry.copy()
    new_entry["action"] = new_action
    return new_entry, "wrong_action"


def mutate_wrong_victim(
    entry: Dict[str, Any], bank: AnswerBank, used_actions: Set[str], **_
) -> Tuple[Optional[Dict[str, Any]], str]:


    if not _is_specific(entry.get("aggressor")) or not _is_specific(entry.get("victim")):
        return None, "wrong_victim"
    exclude = {
        str(entry.get("aggressor", "")).lower(),
        str(entry.get("victim", "")).lower(),
    }
    new_victim = _pick_different_person(bank, exclude)
    if new_victim is None:
        return None, "wrong_victim"
    new_action = _pick_unused_action(bank, used_actions, forbid=entry.get("action"))
    if new_action is None:
        return None, "wrong_victim"
    new_entry = entry.copy()
    new_entry["victim"] = new_victim
    new_entry["action"] = new_action
    return new_entry, "wrong_victim"


def mutate_wrong_aggressor(
    entry: Dict[str, Any], bank: AnswerBank, used_actions: Set[str], **_
) -> Tuple[Optional[Dict[str, Any]], str]:
    if not _is_specific(entry.get("aggressor")) or not _is_specific(entry.get("victim")):
        return None, "wrong_aggressor"
    exclude = {
        str(entry.get("aggressor", "")).lower(),
        str(entry.get("victim", "")).lower(),
    }
    new_aggressor = _pick_different_person(bank, exclude)
    if new_aggressor is None:
        return None, "wrong_aggressor"
    new_action = _pick_unused_action(bank, used_actions, forbid=entry.get("action"))
    if new_action is None:
        return None, "wrong_aggressor"
    new_entry = entry.copy()
    new_entry["aggressor"] = new_aggressor
    new_entry["action"] = new_action
    return new_entry, "wrong_aggressor"


def mutate_bystander_substitution(
    entry: Dict[str, Any], bank: AnswerBank, used_actions: Set[str], **_
) -> Tuple[Optional[Dict[str, Any]], str]:
    specific = _specific_bystanders(entry)
    if not specific:
        return None, "bystander_substitution"
    if not _is_specific(entry.get("aggressor")) and not _is_specific(entry.get("victim")):
        return None, "bystander_substitution"
    bystander = random.choice(specific)
    new_action = _pick_unused_action(bank, used_actions, forbid=entry.get("action"))
    if new_action is None:
        return None, "bystander_substitution"
    new_entry = entry.copy()
    agg_ok = _is_specific(entry.get("aggressor"))
    vic_ok = _is_specific(entry.get("victim"))
    if agg_ok and vic_ok:
        slot = "aggressor" if random.random() < 0.5 else "victim"
    else:
        slot = "aggressor" if agg_ok else "victim"
    new_entry[slot] = bystander
    new_entry["action"] = new_action
    return new_entry, "bystander_substitution"


def mutate_wrong_location(
    entry: Dict[str, Any], bank: AnswerBank, used_actions: Set[str], **_
) -> Tuple[Optional[Dict[str, Any]], str]:
    exclude = {str(entry.get("environment", "")).lower()}
    new_env = _pick_different_environment(bank, exclude)
    if new_env is None:
        return None, "wrong_location"
    new_action = _pick_unused_action(bank, used_actions, forbid=entry.get("action"))
    if new_action is None:
        return None, "wrong_location"
    new_entry = entry.copy()
    new_entry["environment"] = new_env
    new_entry["action"] = new_action
    return new_entry, "wrong_location"


def mutate_wrong_category(
    entry: Dict[str, Any], bank: AnswerBank, used_actions: Set[str], **_
) -> Tuple[Optional[Dict[str, Any]], str]:


    new_action = _pick_unused_action(bank, used_actions, forbid=entry.get("action"))
    if new_action is None:
        return None, "wrong_category"
    exclude_env = {str(entry.get("environment", "")).lower()}
    new_env = _pick_different_environment(bank, exclude_env)
    new_entry = entry.copy()
    new_entry["action"] = new_action
    if new_env is not None:
        new_entry["environment"] = new_env
    return new_entry, "wrong_category"


def mutate_none_claim(
    entry: Dict[str, Any], bank: AnswerBank, used_actions: Set[str], **_
) -> Tuple[Optional[Dict[str, Any]], str]:

    return None, "none_claim"


def mutate_cross_video(
    entry: Dict[str, Any],
    bank: AnswerBank,
    used_actions: Set[str],
    all_annotations: Optional[list] = None,
    **_,
) -> Tuple[Optional[Dict[str, Any]], str]:

    other = _pick_different_annotation(
        all_annotations or [],
        exclude_key=entry.get("file_name") or entry.get("video_name"),
    )
    new_action = _pick_unused_action(bank, used_actions, forbid=entry.get("action"))
    if new_action is None:
        return None, "cross_video"
    new_entry = entry.copy()
    if other is not None:
        new_entry["aggressor"] = other.get("aggressor")
        new_entry["victim"] = other.get("victim")
        if other.get("environment"):
            new_entry["environment"] = other["environment"]
    else:

        exclude_p = {
            str(entry.get("aggressor", "")).lower(),
            str(entry.get("victim", "")).lower(),
        }
        agg = _pick_different_person(bank, exclude_p)
        if agg is None:
            return None, "cross_video"
        exclude_p.add(agg.lower())
        vic = _pick_different_person(bank, exclude_p)
        if vic is None:
            return None, "cross_video"
        new_entry["aggressor"] = agg
        new_entry["victim"] = vic
        new_env = _pick_different_environment(
            bank, {str(entry.get("environment", "")).lower()}
        )
        if new_env is not None:
            new_entry["environment"] = new_env
    new_entry["action"] = new_action
    return new_entry, "cross_video"


MUTATION_BUILDERS = {
    "role_reversal": mutate_role_reversal,
    "wrong_action": mutate_wrong_action,
    "wrong_victim": mutate_wrong_victim,
    "wrong_aggressor": mutate_wrong_aggressor,
    "bystander_substitution": mutate_bystander_substitution,
    "wrong_location": mutate_wrong_location,
    "wrong_category": mutate_wrong_category,
    "none_claim": mutate_none_claim,
    "cross_video": mutate_cross_video,
}

FALLBACK_ORDER = [
    "role_reversal",
    "wrong_action",
    "wrong_victim",
    "wrong_aggressor",
    "bystander_substitution",
    "wrong_location",
    "wrong_category",
    "cross_video",
]


def _scan_emitted_actions(text: str, bank: AnswerBank) -> list[str]:

    lower = text.lower()
    hits: list[str] = []

    for action in sorted(bank.actions, key=len, reverse=True):
        if action.lower() in lower:
            hits.append(action)
    return hits


def build_targeted_distractor(
    requested_category: str,
    entry: Dict[str, Any],
    template,
    used_actions: Set[str],
    used_options: Set[str],
    bank: AnswerBank,
    qtype: str,
    all_annotations: Optional[list] = None,
) -> Tuple[Optional[str], str]:

    if requested_category == "none_claim":
        if template.static_distractor and template.static_distractor.lower() not in used_options:
            return template.static_distractor, "none_claim"
        return None, "none_claim"

    func = MUTATION_BUILDERS.get(requested_category)
    if not func:
        return None, requested_category


    result, actual_category = func(
        entry, bank, used_actions, all_annotations=all_annotations
    )
    if result is None:
        return None, actual_category

    text = template.correct_answer_builder(result)

    if text.lower() in used_options:
        return None, requested_category

    return text, actual_category


def fulfill_recipe(
    recipe,
    entry: Dict[str, Any],
    template,
    correct_answer: str,
    bank: AnswerBank,
    qtype: str,
    all_annotations: Optional[list] = None,
) -> Tuple[list[str], list[str]]:

    slots = recipe.expand()
    random.shuffle(slots)

    used_options = {correct_answer.lower()}


    used_actions: Set[str] = set()
    if entry.get("action"):
        used_actions.add(str(entry["action"]).lower())


    for a in _scan_emitted_actions(correct_answer, bank):
        used_actions.add(a.lower())

    distractors: list[str] = []
    categories: list[str] = []

    for requested_category in slots:
        text, actual_category = build_targeted_distractor(
            requested_category, entry, template, used_actions,
            used_options, bank, qtype, all_annotations=all_annotations,
        )


        if text is None:
            try:
                start_idx = FALLBACK_ORDER.index(requested_category)
            except ValueError:
                start_idx = -1
            for fallback_cat in FALLBACK_ORDER[start_idx + 1:]:
                text, actual_category = build_targeted_distractor(
                    fallback_cat, entry, template, used_actions,
                    used_options, bank, qtype, all_annotations=all_annotations,
                )
                if text is not None:
                    break

        if text is None:
            text, actual_category = build_targeted_distractor(
                "cross_video", entry, template, used_actions,
                used_options, bank, qtype, all_annotations=all_annotations,
            )

        if text is not None:
            distractors.append(text)
            categories.append(actual_category)
            used_options.add(text.lower())


            for a in _scan_emitted_actions(text, bank):
                used_actions.add(a.lower())

    return distractors, categories
