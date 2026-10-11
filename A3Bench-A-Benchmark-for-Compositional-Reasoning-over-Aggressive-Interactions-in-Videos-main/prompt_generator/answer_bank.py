from dataclasses import dataclass, field

from .templates import COUNT_OPTIONS, _format_people


@dataclass
class AnswerBank:
    people: set = field(default_factory=set)
    environments: set = field(default_factory=set)
    actions: set = field(default_factory=set)
    action_statements: set = field(default_factory=set)
    action_by_role: set = field(default_factory=set)
    compound_aggressor_location: set = field(default_factory=set)
    compound_action_victims: set = field(default_factory=set)
    compound_action_aggressor: set = field(default_factory=set)
    compound_action_location: set = field(default_factory=set)
    compound_aggressor_victim: set = field(default_factory=set)
    compound_bystander_location: set = field(default_factory=set)
    compound_aggressor_victim_count: set = field(default_factory=set)
    compound_victim_bystander_count: set = field(default_factory=set)
    compound_aggressor_action_victim: set = field(default_factory=set)
    action_frequencies: dict = field(default_factory=dict)

    @classmethod
    def from_annotations(cls, annotations: list[dict]) -> "AnswerBank":
        bank = cls()
        for entry in annotations:
            normalized = normalize_entry(entry)
            bank._extract_people(normalized)
            bank._extract_environment(normalized)
            bank._extract_action(normalized)
            bank._extract_action_statements(normalized)
            bank._extract_action_by_role(normalized)
            bank._extract_compound_answers(normalized)

        bank._expand_compound_count_pools()
        return bank

    def _extract_people(self, entry: dict) -> None:
        for key in ("aggressor", "victim", "bystander"):
            value = entry.get(key)
            if value:
                self._add_people(value)

    def _add_people(self, value) -> None:
        if isinstance(value, list):
            for person in value:
                if person and isinstance(person, str) and person.strip():
                    self.people.add(person.strip())
        elif isinstance(value, str) and value.strip():
            self.people.add(value.strip())

    def _extract_environment(self, entry: dict) -> None:
        env = entry.get("environment")
        if env and isinstance(env, str) and env.strip():
            self.environments.add(env.strip())

    def _extract_action(self, entry: dict) -> None:
        action = entry.get("action")
        if action and isinstance(action, str) and action.strip():
            cleaned = action.strip()


            # for the synthetic negative-question generator but must NOT enter
            # the action pool -- otherwise a random distractor could read as

            if cleaned.lower() == "none":
                return
            self.actions.add(cleaned)
            self.action_frequencies[cleaned] = self.action_frequencies.get(cleaned, 0) + 1

    def get_action_weights(self) -> dict[str, float]:

        if not self.action_frequencies:
            return {}
        max_freq = max(self.action_frequencies.values())
        return {
            action: max_freq / freq
            for action, freq in self.action_frequencies.items()
        }

    def _extract_action_statements(self, entry: dict) -> None:
        action = entry.get("action")
        if not action:
            return

        aggressor = _format_people(entry.get("aggressor"))
        victim = _format_people(entry.get("victim"))
        bystander = _format_people(entry.get("bystander"))

        if aggressor and victim:
            self.action_statements.add(
                f"{aggressor} performs action of {action} on {victim}"
            )
        if victim and aggressor:
            self.action_statements.add(
                f"{victim} performs action of {action} on {aggressor}"
            )
        if bystander and victim:
            self.action_statements.add(
                f"{bystander} performs action of {action} on {victim}"
            )
        if victim and bystander:
            self.action_statements.add(
                f"{victim} performs action of {action} on {bystander}"
            )

    def _extract_action_by_role(self, entry: dict) -> None:
        for key in ("aggressor", "victim", "bystander"):
            value = entry.get(key)
            if value:
                formatted = _format_people(value)
                if formatted:
                    self.action_by_role.add(f"The action performed by {formatted}")

    def _extract_compound_answers(self, entry: dict) -> None:

        aggressor = _format_people(entry.get("aggressor"))
        victim = _format_people(entry.get("victim"))
        bystander = _format_people(entry.get("bystander"))
        environment = entry.get("environment")
        action = entry.get("action")
        outcome = entry.get("outcome")


        if aggressor and environment:
            self.compound_aggressor_location.add(f"{aggressor} in {environment}")
        if aggressor and not environment:
            self.compound_aggressor_location.add(f"{aggressor}; location unclear")
        if not aggressor and environment:
            self.compound_aggressor_location.add(f"No aggressor present; location is {environment}")


        if action:
            if victim:
                self.compound_action_victims.add(f"{action}; Victim: {victim}")
            else:
                self.compound_action_victims.add(f"{action}; Victim: No one appears to be victimized")


        if action:
            if aggressor:
                self.compound_action_aggressor.add(f"{action}; Aggressor: {aggressor}")
            else:
                self.compound_action_aggressor.add(f"{action}; Aggressor: No aggressor present")


        if action and environment:
            self.compound_action_location.add(f"{action} in {environment}")
        if action and not environment:
            self.compound_action_location.add(f"{action} in unclear location")
        if not action and environment:
            self.compound_action_location.add(f"No action in {environment}")


        if aggressor and victim:
            self.compound_aggressor_victim.add(f"Aggressor: {aggressor}; Victim: {victim}")
        if aggressor and not victim:
            self.compound_aggressor_victim.add(f"Aggressor: {aggressor}; No victim")
        if not aggressor and victim:
            self.compound_aggressor_victim.add(f"No aggressor; Victim: {victim}")


        if bystander and environment:
            self.compound_bystander_location.add(f"{bystander} in {environment}")
        if bystander and not environment:
            self.compound_bystander_location.add(f"{bystander} in unclear location")
        if not bystander and environment:
            self.compound_bystander_location.add(f"No bystanders in {environment}")


        agg_count = self._count_people(entry.get("aggressor"))
        vic_count = self._count_people(entry.get("victim"))
        agg_text = f"{agg_count} aggressor" + ("s" if agg_count != 1 else "")
        vic_text = f"{vic_count} victim" + ("s" if vic_count != 1 else "")
        self.compound_aggressor_victim_count.add(f"{agg_text} and {vic_text}")


        bys_count = self._count_people(entry.get("bystander"))
        vic_text = f"{vic_count} victim" + ("s" if vic_count != 1 else "")
        bys_text = f"{bys_count} bystander" + ("s" if bys_count != 1 else "")
        self.compound_victim_bystander_count.add(f"{vic_text} and {bys_text}")


        if aggressor and action and victim:
            self.compound_aggressor_action_victim.add(f"{aggressor} performed {action} on {victim}")
        if aggressor and action and not victim:
            self.compound_aggressor_action_victim.add(f"{aggressor} performed {action} on unknown target")

    def _expand_compound_count_pools(self) -> None:

        agg_victim_combos = [
            f"{a} aggressor{'s' if a != 1 else ''} and {v} victim{'s' if v != 1 else ''}"
            for a in range(4) for v in range(4)
        ]
        for combo in agg_victim_combos:
            self.compound_aggressor_victim_count.add(combo)

        victim_bystander_combos = [
            f"{v} victim{'s' if v != 1 else ''} and {b} bystander{'s' if b != 1 else ''}"
            for v in range(4) for b in range(4)
        ]
        for combo in victim_bystander_combos:
            self.compound_victim_bystander_count.add(combo)

    def _count_people(self, value) -> int:

        if value is None:
            return 0
        if isinstance(value, list):
            return len([v for v in value if v])
        if isinstance(value, str) and value.strip():
            return 1
        return 0

    def get_pool(self, pool_name: str) -> list:
        pool_map = {
            "people": self.people,
            "environments": self.environments,
            "actions": self.actions,
            "action_statements": self.action_statements,
            "action_by_role": self.action_by_role,
            "compound_aggressor_location": self.compound_aggressor_location,
            "compound_action_victims": self.compound_action_victims,
            "compound_action_aggressor": self.compound_action_aggressor,
            "compound_action_location": self.compound_action_location,
            "compound_aggressor_victim": self.compound_aggressor_victim,
            "compound_bystander_location": self.compound_bystander_location,
            "compound_aggressor_victim_count": self.compound_aggressor_victim_count,
            "compound_victim_bystander_count": self.compound_victim_bystander_count,
            "compound_aggressor_action_victim": self.compound_aggressor_action_victim,
            "counts": COUNT_OPTIONS,
        }
        pool = pool_map.get(pool_name, set())
        return list(pool)


def normalize_entry(entry: dict) -> dict:
    normalized = dict(entry)


    if "file_name" in normalized and "video_name" not in normalized:
        normalized["video_name"] = normalized.pop("file_name")


    if "bystanders" in normalized and "bystander" not in normalized:
        normalized["bystander"] = normalized.pop("bystanders")
    if "aggressors" in normalized and "aggressor" not in normalized:
        normalized["aggressor"] = normalized.pop("aggressors")
    if "victims" in normalized and "victim" not in normalized:
        normalized["victim"] = normalized.pop("victims")


    none_values = {"none", "None", "NONE", "n/a", "N/A", ""}
    for key in ["aggressor", "victim", "bystander", "environment", "action"]:
        if key in normalized:
            value = normalized[key]
            if isinstance(value, str) and value.strip().lower() in none_values:
                normalized[key] = None
            elif isinstance(value, list):

                filtered = [v for v in value if not (isinstance(v, str) and v.strip().lower() in none_values)]
                normalized[key] = filtered if filtered else None


    ACTION_SYNONYMS = {
        "talking aggressively": "aggressive talking",
        "grab clothing": "clothing grab",
    }
    if normalized.get("action") and isinstance(normalized["action"], str):
        action_lower = normalized["action"].strip().lower()
        if action_lower in ACTION_SYNONYMS:
            normalized["action"] = ACTION_SYNONYMS[action_lower]


    for key in ["aggressor", "victim", "bystander"]:
        value = normalized.get(key)
        if isinstance(value, str) and value and value[0].isupper():
            if value.lower().startswith("person"):
                normalized[key] = value[0].lower() + value[1:]
        elif isinstance(value, list):
            normalized[key] = [
                (v[0].lower() + v[1:]) if isinstance(v, str) and v and v.lower().startswith("person") and v[0].isupper() else v
                for v in value
            ]

    return normalized


