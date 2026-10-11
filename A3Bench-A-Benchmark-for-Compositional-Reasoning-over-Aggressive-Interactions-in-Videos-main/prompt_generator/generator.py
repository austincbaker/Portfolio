import random

import re
from dataclasses import dataclass

from .answer_bank import AnswerBank, normalize_entry
from prompt_generator.hardness import (
    DEFAULT_RECIPES,
    HardnessRecipe,
    TRICK_RECIPE_FACTORY,
)
from prompt_generator.mutations import fulfill_recipe
from .templates import (
    QUESTION_TEMPLATES,
    COUNT_OPTIONS,
    ROLE_LABELS,
    ROLE_ID_NO_MATCH,
    SEQ_ORIGINAL_CORRECT,
    SEQ_NO_MATCH,
    QuestionType,
    QuestionTemplate,
    _format_people,
    _specific_bystander,
    _individual_bystanders,
)


@dataclass
class GeneratedQuestion:
    video_name: str
    question_type: str
    prompt: str
    answers: list[str]
    correct_answer: str
    correct_index: int
    is_trick: bool = False
    option_hardness: list[str] = None


NONE_DISTRACTOR_INJECTION_RATE = 0.20

class QuestionGenerator:
    def __init__(self, annotations: list[dict], num_distractors: int = 7, trick_probability: float = 0.0, recipes: dict = None):
        self.annotations = [normalize_entry(e) for e in annotations]
        self.bank = AnswerBank.from_annotations(annotations)
        self.num_distractors = num_distractors
        self.trick_probability = trick_probability
        self._recipes = recipes if recipes is not None else DEFAULT_RECIPES
        self._trick_counts: dict[str, int] = {}
        self._total_counts: dict[str, int] = {}


        self._sorted_actions: list[str] = sorted(self.bank.actions, key=len, reverse=True)

        self._action_patterns: dict[str, "re.Pattern"] = {
            a: re.compile(re.escape(a), re.IGNORECASE) for a in self._sorted_actions
        }

    def _option_action(self, option: str) -> str | None:

        if not self._sorted_actions:
            return None
        lower = option.lower()
        for act in self._sorted_actions:
            if act.lower() in lower:
                return act
        return None

    def _rewrite_action(self, option: str, old_action: str, new_action: str) -> str:

        pattern = self._action_patterns.get(old_action)
        if pattern is None:
            pattern = re.compile(re.escape(old_action), re.IGNORECASE)
        return pattern.sub(new_action, option, count=1)

    def _enforce_unique_actions(self, answers: list[str]) -> list[str]:

        if not self._sorted_actions:
            return list(answers)
        used: set[str] = set()
        result: list[str] = []
        for ans in answers:
            act = self._option_action(ans)
            if act is None:
                result.append(ans)
                continue
            if act not in used:
                used.add(act)
                result.append(ans)
                continue

            candidates = [a for a in self._sorted_actions if a not in used]
            if not candidates:


                result.append(ans)
                continue
            new_action = random.choice(candidates)
            used.add(new_action)
            result.append(self._rewrite_action(ans, act, new_action))
        return result

    def _enforce_unique_actions_with_labels(
        self, answers: list[str], option_hardness: list[str], correct_answer: str,
        qtype: str, entry: dict,
    ) -> tuple[list[str], list[str]]:

        rewritten = self._enforce_unique_actions(answers)
        if rewritten == answers:
            return rewritten, option_hardness

        from prompt_generator.hardness import classify_distractor
        new_labels = list(option_hardness)
        for i, (orig, new) in enumerate(zip(answers, rewritten)):
            if orig == new:
                continue
            if option_hardness[i] == "correct":
                # Correct answer's text should never be rewritten -- defensive

                continue
            new_labels[i] = classify_distractor(qtype, new, correct_answer, entry)
        return rewritten, new_labels

    @staticmethod
    def _length_balanced_sample(
        pool: list[str],
        target_length: int,
        count: int,
        tolerance: float = 0.4,
    ) -> list[str]:

        if not pool or count <= 0:
            return []

        close = []
        far = []
        lower = target_length * (1 - tolerance)
        upper = target_length * (1 + tolerance)

        for item in pool:
            if lower <= len(item) <= upper:
                close.append(item)
            else:
                far.append(item)

        random.shuffle(close)
        random.shuffle(far)

        result = close[:count]
        if len(result) < count:
            result.extend(far[: count - len(result)])
        return result

    @staticmethod
    def _is_semantically_similar(answer1: str, answer2: str) -> bool:

        if answer1 is None or answer2 is None:
            return False


        a1 = answer1.lower().strip()
        a2 = answer2.lower().strip()


        if a1 == a2:
            return True


        none_keywords = {
            "no one", "no individual", "no person", "no people",
            "no bystander", "no victim", "no aggressor",
            "none", "not present", "no action",
            "not shown", "unclear", "not visible",
            "no meaningful", "no sequence"
        }


        a1_is_none = any(keyword in a1 for keyword in none_keywords)
        a2_is_none = any(keyword in a2 for keyword in none_keywords)

        if a1_is_none and a2_is_none:
            return True

        if len(a1) > 10 and len(a2) > 10:
            if a1 in a2 or a2 in a1:
                return True

        return False



    _PREFIX_SEPARATORS = ("; ", " in ")

    @staticmethod
    def _extract_prefix(answer: str) -> str | None:

        if "; " in answer:
            return answer.split("; ", 1)[0].strip()
        if " in " in answer:
            \
            idx = answer.rfind(" in ")
            if idx > 0:
                return answer[:idx].strip()
        return None

    def _cap_prefix_repeats(
        self,
        correct_answer: str,
        distractors: list[str],
        pool_name: str | None = None,
        max_prefix_repeat: int = 2,
    ) -> list[str]:

        correct_prefix = QuestionGenerator._extract_prefix(correct_answer)
        if correct_prefix is None:
            return distractors

        correct_prefix_lower = correct_prefix.lower()


        from collections import Counter
        prefix_counts: Counter[str] = Counter()
        prefix_counts[correct_prefix_lower] += 1

        matching_indices: list[int] = []
        for i, d in enumerate(distractors):
            d_prefix = QuestionGenerator._extract_prefix(d)
            if d_prefix is not None:
                p_lower = d_prefix.lower()
                prefix_counts[p_lower] += 1
                if p_lower == correct_prefix_lower:
                    matching_indices.append(i)


        other_max = 0
        for prefix, count in prefix_counts.items():
            if prefix != correct_prefix_lower and count > other_max:
                other_max = count


        correct_total = prefix_counts[correct_prefix_lower]
        if correct_total <= max(other_max, 1):
            return distractors



        target_distractors = max(other_max, 1) - 1
        target_distractors = max(target_distractors, 0)

        if len(matching_indices) <= target_distractors:
            return distractors


        existing = {d.lower() for d in distractors} | {correct_answer.lower()}
        replacements: list[str] = []
        if pool_name is not None:
            pool = self.bank.get_pool(pool_name)
            random.shuffle(pool)
            for item in pool:
                if item.lower() in existing:
                    continue
                item_prefix = QuestionGenerator._extract_prefix(item)
                if item_prefix is not None and item_prefix.lower() == correct_prefix_lower:
                    continue
                if self._is_semantically_similar(item, correct_answer):
                    continue
                replacements.append(item)

        random.shuffle(matching_indices)
        keep = set(matching_indices[:target_distractors])
        evict_indices = [i for i in matching_indices if i not in keep]

        result = list(distractors)
        replaced = 0

        for idx in evict_indices:
            if replaced < len(replacements):
                result[idx] = replacements[replaced]
                replaced += 1
            else:
                result[idx] = None


        result = [d for d in result if d is not None]

        return result

    def _should_be_trick(self, question_type: str) -> bool:

        if self.trick_probability <= 0:
            return False

        total = self._total_counts.get(question_type, 0)
        tricks = self._trick_counts.get(question_type, 0)

        if total < 4:
            return random.random() < self.trick_probability
        else:
            current_rate = tricks / total
            if current_rate > self.trick_probability:
                adjusted_prob = self.trick_probability * 0.5
            elif current_rate < self.trick_probability * 0.5:
                adjusted_prob = min(self.trick_probability * 1.5, 0.5)
            else:
                adjusted_prob = self.trick_probability
            return random.random() < adjusted_prob

    def _record_trick_outcome(self, question_type: str, was_trick: bool) -> None:

        self._total_counts[question_type] = self._total_counts.get(question_type, 0) + 1
        if was_trick:
            self._trick_counts[question_type] = self._trick_counts.get(question_type, 0) + 1

    def generate_question(
        self, entry: dict | None = None, question_type: QuestionType | None = None
    ) -> GeneratedQuestion | None:
        if entry is None:
            entry = random.choice(self.annotations)
        entry = normalize_entry(entry)

        if question_type is None:
            question_type = random.choice(list(QuestionType))

        if question_type == QuestionType.ROLE_IDENTIFICATION:
            return self._generate_role_identification(entry)

        if question_type == QuestionType.SEQUENCE_VERIFICATION:
            return self._generate_sequence_verification(entry)

        template = QUESTION_TEMPLATES[question_type]
        if not self._has_required_fields(entry, template):
            available_types = self._get_valid_question_types(entry)
            if not available_types:
                return None
            question_type = random.choice(available_types)
            template = QUESTION_TEMPLATES[question_type]

        return self._generate_from_template(entry, template)

    def generate_questions(
        self, count: int, allow_duplicates: bool = False
    ) -> list[GeneratedQuestion]:
        questions = []
        used_combinations = set()

        attempts = 0
        max_attempts = count * 10

        while len(questions) < count and attempts < max_attempts:
            attempts += 1
            question = self.generate_question()
            if question is None:
                continue

            combo_key = (question.video_name, question.question_type, question.prompt)
            if not allow_duplicates and combo_key in used_combinations:
                continue

            used_combinations.add(combo_key)
            questions.append(question)

        return questions

    def generate_all_questions(self) -> list[GeneratedQuestion]:

        questions = []

        for entry in self.annotations:
            valid_types = self._get_valid_question_types(entry)

            for question_type in valid_types:
                question = self.generate_question(entry=entry, question_type=question_type)
                if question is not None:
                    questions.append(question)

        return questions

    def generate_distributed_questions_for_video(
        self,
        entry: dict,
        distributor: "CategoryDistributor",
    ) -> list[GeneratedQuestion]:

        from .distribution import CategoryDistributor

        selected_types = distributor.select_questions_for_video(entry, self)

        questions = []
        for qtype in selected_types:
            question = self.generate_question(entry=entry, question_type=qtype)
            if question is not None:
                questions.append(question)

        return questions

    def _get_same_video_people_distractors(
        self, entry: dict, exclude_role: str
    ) -> list[str]:

        distractors = []
        seen = set()
        for role in ("aggressor", "victim", "bystander"):
            if role == exclude_role:
                continue
            value = entry.get(role)
            if value is None:
                continue
            if isinstance(value, list):
                for person in value:
                    if person and isinstance(person, str) and person.strip():
                        if role == "bystander" and "group of" in person.lower():
                            continue
                        key = person.strip().lower()
                        if key not in seen:
                            distractors.append(person.strip())
                            seen.add(key)
            elif isinstance(value, str) and value.strip():
                if role == "bystander" and "group of" in value.lower():
                    continue
                key = value.strip().lower()
                if key not in seen:
                    distractors.append(value.strip())
                    seen.add(key)
        return distractors

    def _generate_from_template(
        self, entry: dict, template: QuestionTemplate
    ) -> GeneratedQuestion | None:
        correct_answer = template.correct_answer_builder(entry)

        if (
            template.static_distractor is not None
            and self._is_semantically_similar(correct_answer, template.static_distractor)
        ):
            if self._should_be_trick(template.question_type.value):
                result = self._generate_trick_from_template(entry, template)
                self._record_trick_outcome(template.question_type.value, True)
                return result
            else:
                return None

        is_trick = template.static_distractor is not None and self._should_be_trick(template.question_type.value)
        if is_trick:
            result = self._generate_trick_from_template(entry, template)
            self._record_trick_outcome(template.question_type.value, True)
            return result

        if template.distractors_override_builder is not None:
            distractors = template.distractors_override_builder(
                entry, self.bank, self.num_distractors, correct_answer,
            )
            answers = [correct_answer] + distractors
            option_hardness = ["correct"] + ["cross_video"] * len(distractors)
            paired = list(zip(answers, option_hardness))
            random.shuffle(paired)
            answers, option_hardness = map(list, zip(*paired))
            correct_index = option_hardness.index("correct")
            self._record_trick_outcome(template.question_type.value, False)
            return GeneratedQuestion(
                video_name=entry.get("video_name", "unknown"),
                question_type=template.question_type.value,
                prompt=template.prompt,
                answers=answers,
                correct_answer=correct_answer,
                correct_index=correct_index,
                is_trick=False,
                option_hardness=option_hardness,
            )

        recipe = self._recipes.get(template.question_type.value)
        if not recipe:
            \
            recipe = HardnessRecipe({"cross_video": self.num_distractors})




        # because this mode deliberately repeats actions across distractors.
        if getattr(recipe, "mode", "standard") == "frequency_inverted":
            from prompt_generator.frequency_inverted import build_frequency_inverted_question

            built = build_frequency_inverted_question(
                entry=entry, template=template, bank=self.bank,
                num_distractors=self.num_distractors,
            )
            if built is not None:
                answers, option_hardness, correct_index = built
                self._record_trick_outcome(template.question_type.value, False)
                return GeneratedQuestion(
                    video_name=entry.get("video_name", "unknown"),
                    question_type=template.question_type.value,
                    prompt=template.prompt,
                    answers=answers,
                    correct_answer=correct_answer,
                    correct_index=correct_index,
                    is_trick=False,
                    option_hardness=option_hardness,
                )
            recipe = DEFAULT_RECIPES.get(
                template.question_type.value,
                HardnessRecipe({"cross_video": self.num_distractors}),
            )

        distractors, categories = fulfill_recipe(
            recipe=recipe,
            entry=entry,
            template=template,
            correct_answer=correct_answer,
            bank=self.bank,
            qtype=template.question_type.value,
            all_annotations=self.annotations,
        )

        answers = [correct_answer] + distractors
        option_hardness = ["correct"] + categories




        answers, option_hardness = self._enforce_unique_actions_with_labels(
            answers, option_hardness, correct_answer,
            template.question_type.value, entry,
        )

        paired = list(zip(answers, option_hardness))
        random.shuffle(paired)
        answers, option_hardness = map(list, zip(*paired))
        correct_index = option_hardness.index("correct")

        self._record_trick_outcome(template.question_type.value, False)
        return GeneratedQuestion(
            video_name=entry.get("video_name", "unknown"),
            question_type=template.question_type.value,
            prompt=template.prompt,
            answers=answers,
            correct_answer=correct_answer,
            correct_index=correct_index,
            is_trick=False,
            option_hardness=option_hardness,
        )

    def _generate_trick_from_template(
        self, entry: dict, template: QuestionTemplate
    ) -> GeneratedQuestion:
        correct_answer = template.static_distractor
        actual_correct = template.correct_answer_builder(entry)

        recipe = TRICK_RECIPE_FACTORY(self.num_distractors)
        distractors, categories = fulfill_recipe(
            recipe=recipe,
            entry=entry,
            template=template,
            correct_answer=correct_answer,
            bank=self.bank,
            qtype=template.question_type.value,
            all_annotations=self.annotations,
        )

        \
        while len(distractors) < self.num_distractors:
            distractors.append(f"Option {len(distractors)+2}")
            categories.append("cross_video")

        answers = [correct_answer] + distractors
        option_hardness = ["correct"] + categories
        answers, option_hardness = self._enforce_unique_actions_with_labels(
            answers, option_hardness, correct_answer,
            template.question_type.value, entry,
        )

        paired = list(zip(answers, option_hardness))
        random.shuffle(paired)
        answers, option_hardness = map(list, zip(*paired))
        correct_index = option_hardness.index("correct")

        return GeneratedQuestion(
            video_name=entry.get("video_name", "unknown"),
            question_type=template.question_type.value,
            prompt=template.prompt,
            answers=answers,
            correct_answer=correct_answer,
            correct_index=correct_index,
            is_trick=True,
            option_hardness=option_hardness,
        )
    def _sample_distractors(
        self,
        pool_name: str,
        correct_answer: str,
        static_distractor: str | None = None,
        priority_distractors: list[str] | None = None,
        same_video_only: bool = False,
    ) -> list[str]:
        pool = self.bank.get_pool(pool_name)

        \
        pool = [
            p for p in pool
            if p != correct_answer and not self._is_semantically_similar(p, correct_answer)
        ]

        sampled: list[str] = []
        seen: set[str] = set()


        if priority_distractors:
            for p in priority_distractors:
                if (
                    p != correct_answer
                    and not self._is_semantically_similar(p, correct_answer)
                    and p.lower() not in seen
                ):
                    sampled.append(p)
                    seen.add(p.lower())


        use_static = False
        if static_distractor and not self._is_semantically_similar(
            static_distractor, correct_answer
        ):
            if static_distractor.lower() not in seen:
                use_static = True



        slots_taken = len(sampled) + (1 if use_static else 0)
        remaining_needed = max(0, self.num_distractors - slots_taken)

        \
        pool = [p for p in pool if p.lower() not in seen]

        if not same_video_only and pool and remaining_needed > 0:
            sample_count = min(remaining_needed, len(pool))
            if pool_name == "actions" and self.bank.action_frequencies:

                weights = self.bank.get_action_weights()
                weighted_pool = [(p, weights.get(p, 1.0)) for p in pool]
                selected_from_pool = []
                for _ in range(sample_count):
                    if not weighted_pool:
                        break
                    total_w = sum(w for _, w in weighted_pool)
                    r = random.random() * total_w
                    cumulative = 0
                    for idx, (item, w) in enumerate(weighted_pool):
                        cumulative += w
                        if r <= cumulative:
                            selected_from_pool.append(item)
                            weighted_pool.pop(idx)
                            break
                sampled.extend(selected_from_pool)
            else:
                balanced = self._length_balanced_sample(
                    pool, len(correct_answer), sample_count
                )
                if balanced:
                    sampled.extend(balanced)
                else:
                    sampled.extend(random.sample(pool, sample_count))
            for p in sampled[len(sampled) - sample_count:]:
                seen.add(p.lower())

        if use_static:
            sampled.append(static_distractor)

\




        if not same_video_only:
            while len(sampled) < self.num_distractors:
                generic = f"Option {len(sampled) + 2}"
                if generic not in sampled and not self._is_semantically_similar(
                    generic, correct_answer
                ):
                    sampled.append(generic)
                else:
                    sampled.append(f"Alternative {len(sampled) + 2}")

\

        return sampled

    def _has_required_fields(self, entry: dict, template: QuestionTemplate) -> bool:

        for field in template.requires_fields:
            \
            if field not in entry:
                return False

            value = entry.get(field)


            if value is None:
                continue


            if isinstance(value, str) and not value.strip():
                return False
            if isinstance(value, list) and not any(
                v and str(v).strip() for v in value
            ):
                return False

        return True

    def _get_valid_question_types(self, entry: dict) -> list[QuestionType]:
        valid = []
        for qtype, template in QUESTION_TEMPLATES.items():
            if self._has_required_fields(entry, template):
                valid.append(qtype)
        if self._can_generate_role_identification(entry):
            valid.append(QuestionType.ROLE_IDENTIFICATION)
        if self._can_generate_sequence_verification(entry):
            valid.append(QuestionType.SEQUENCE_VERIFICATION)
        return valid

    def _can_generate_role_identification(self, entry: dict) -> bool:

        for role in ("aggressor", "victim", "bystander"):
            value = entry.get(role)
            if value is None:
                continue
            if isinstance(value, list):
                for person in value:
                    if person and isinstance(person, str) and "group of" not in person.lower():
                        return True
            elif isinstance(value, str) and value.strip() and "group of" not in value.lower():
                return True
        return False

    def _generate_role_identification(
        self, entry: dict
    ) -> GeneratedQuestion | None:

        candidates = []
        for role in ("aggressor", "victim", "bystander"):
            value = entry.get(role)
            if value is None:
                continue
            label = role.capitalize()
            if isinstance(value, list):
                for person in value:
                    if person and isinstance(person, str) and "group of" not in person.lower():
                        candidates.append((label, person.strip()))
            elif isinstance(value, str) and value.strip() and "group of" not in value.lower():
                candidates.append((label, value.strip()))

        if not candidates:
            return None

        current_descriptions = set()
        for role in ("aggressor", "victim", "bystander"):
            value = entry.get(role)
            if value is None:
                continue
            if isinstance(value, list):
                for person in value:
                    if person and isinstance(person, str):
                        current_descriptions.add(person.strip().lower())
            elif isinstance(value, str) and value.strip():
                current_descriptions.add(value.strip().lower())

        is_trick = self._should_be_trick(QuestionType.ROLE_IDENTIFICATION.value)

        if is_trick:
            foreign_pool = [
                desc for desc in self.bank.people
                if desc.strip().lower() not in current_descriptions
            ]
            if not foreign_pool:
                is_trick = False

        if is_trick:
            person_desc = random.choice(foreign_pool)
            correct_answer = ROLE_ID_NO_MATCH
            distractors = random.sample(ROLE_LABELS, min(self.num_distractors, len(ROLE_LABELS)))
            categories = ["cross_video"] * len(distractors)
        else:
            correct_role, person_desc = random.choice(candidates)
            correct_answer = correct_role
            other_labels = [l for l in ROLE_LABELS if l != correct_role]
            num_label_distractors = self.num_distractors - 1
            sampled_labels = random.sample(other_labels, min(num_label_distractors, len(other_labels)))
            distractors = sampled_labels + [ROLE_ID_NO_MATCH]

            categories = []
            for d in distractors:
                if d == ROLE_ID_NO_MATCH:
                    categories.append("none_claim")
                elif d == "Aggressor" or d == "Victim":
                    categories.append("role_reversal")
                elif d == "Bystander":
                    categories.append("bystander_substitution")
                else:
                    categories.append("cross_video")

        prompt = f"Concerning the {person_desc}, their role would best be described as:"

        answers = [correct_answer] + distractors
        option_hardness = ["correct"] + categories

        paired = list(zip(answers, option_hardness))

        random.shuffle(paired)
        answers, option_hardness = map(list, zip(*paired))
        correct_index = option_hardness.index("correct")

        self._record_trick_outcome(QuestionType.ROLE_IDENTIFICATION.value, is_trick)
        return GeneratedQuestion(
            video_name=entry.get("video_name", "unknown"),
            question_type=QuestionType.ROLE_IDENTIFICATION.value,
            prompt=prompt,
            answers=answers,
            correct_answer=correct_answer,
            correct_index=correct_index,
            is_trick=is_trick,
            option_hardness=option_hardness
        )
    def _can_generate_sequence_verification(self, entry: dict) -> bool:

        aggressor_raw = entry.get("aggressor")
        victim_raw = entry.get("victim")
        action = entry.get("action")
        # Guard against empty lists that would crash _format_people
        if isinstance(aggressor_raw, list) and not aggressor_raw:
            return False
        if isinstance(victim_raw, list) and not victim_raw:
            return False
        aggressor = _format_people(aggressor_raw)
        victim = _format_people(victim_raw)
        return aggressor is not None and action is not None and victim is not None

    @staticmethod
    def _build_sequence_str(aggressor: str, action: str, victim: str, style: int = 0) -> str:
        if style == 0:
            return (
                f"{aggressor}, who is the aggressor, performed the action of "
                f"{action} against {victim} who is the victim"
            )
        elif style == 1:
            return (
                f"The aggressor, {aggressor}, carried out {action} "
                f"against the victim, {victim}"
            )
        else:
            return (
                f"{aggressor} (aggressor) did {action} to {victim} (victim)"
            )

    def _generate_alternate_sequences(
        self, correct_seq: str, count: int, exclude: set[str] | None = None, style: int = 0
    ) -> list[str]:

        people_pool = list(self.bank.people)
        actions_pool = list(self.bank.actions)
        excluded = {correct_seq} | (exclude or set())
        alternates = set()
        attempts = 0
        max_attempts = count * 10

        while len(alternates) < count and attempts < max_attempts:
            attempts += 1
            alt_agg = random.choice(people_pool)
            alt_action = random.choice(actions_pool)
            alt_vic = random.choice(people_pool)
            seq = self._build_sequence_str(alt_agg, alt_action, alt_vic, style)
            if seq not in excluded:
                alternates.add(seq)

        return list(alternates)[:count]

    def _generate_sequence_verification(
        self, entry: dict
    ) -> GeneratedQuestion | None:

        aggressor = _format_people(entry.get("aggressor"))
        action = entry.get("action")
        victim = _format_people(entry.get("victim"))

        if aggressor is None or action is None or victim is None:
            return None

        seq_style = random.randint(0, 2)
        prompt = "Which of the following sequences best describes the interaction shown in the video?"

        def _seq_builder(e: dict) -> str:
            agg = _format_people(e.get("aggressor")) or "Unknown"
            act = e.get("action") or "unknown action"
            vic = _format_people(e.get("victim")) or "unknown target"
            return self._build_sequence_str(agg, act, vic, seq_style)

        is_trick = self._should_be_trick(QuestionType.SEQUENCE_VERIFICATION.value)



        shim_template = QuestionTemplate(
            question_type=QuestionType.SEQUENCE_VERIFICATION,
            prompt=prompt,
            correct_answer_builder=_seq_builder,
            distractor_pool="",
            static_distractor=SEQ_NO_MATCH if is_trick else None,
        )

        if is_trick:


            correct_answer = SEQ_NO_MATCH
            recipe = TRICK_RECIPE_FACTORY(self.num_distractors)
        else:
            correct_answer = _seq_builder(entry)
            recipe = self._recipes.get(
                QuestionType.SEQUENCE_VERIFICATION.value,
                HardnessRecipe({"cross_video": self.num_distractors}),
            )



        if not is_trick and getattr(recipe, "mode", "standard") == "frequency_inverted":
            from prompt_generator.frequency_inverted import build_frequency_inverted_question

            built = build_frequency_inverted_question(
                entry=entry, template=shim_template, bank=self.bank,
                num_distractors=self.num_distractors,
            )
            if built is not None:
                answers, option_hardness, correct_index = built
                self._record_trick_outcome(QuestionType.SEQUENCE_VERIFICATION.value, False)
                return GeneratedQuestion(
                    video_name=entry.get("video_name", "unknown"),
                    question_type=QuestionType.SEQUENCE_VERIFICATION.value,
                    prompt=prompt,
                    answers=answers,
                    correct_answer=correct_answer,
                    correct_index=correct_index,
                    is_trick=False,
                    option_hardness=option_hardness,
                )

            recipe = DEFAULT_RECIPES.get(
                QuestionType.SEQUENCE_VERIFICATION.value,
                HardnessRecipe({"cross_video": self.num_distractors}),
            )

        distractors, categories = fulfill_recipe(
            recipe=recipe,
            entry=entry,
            template=shim_template,
            correct_answer=correct_answer,
            bank=self.bank,
            qtype=QuestionType.SEQUENCE_VERIFICATION.value,
            all_annotations=self.annotations,
        )



        while len(distractors) < self.num_distractors:
            alts = self._generate_alternate_sequences(
                correct_answer, self.num_distractors - len(distractors),
                exclude=set(distractors) | {correct_answer}, style=seq_style,
            )
            if not alts:
                break
            for alt in alts:
                distractors.append(alt)
                categories.append("cross_video")

        answers = [correct_answer] + distractors
        option_hardness = ["correct"] + categories
        answers, option_hardness = self._enforce_unique_actions_with_labels(
            answers, option_hardness, correct_answer,
            QuestionType.SEQUENCE_VERIFICATION.value, entry,
        )

        paired = list(zip(answers, option_hardness))
        random.shuffle(paired)
        answers, option_hardness = map(list, zip(*paired))
        correct_index = answers.index(correct_answer)

        self._record_trick_outcome(QuestionType.SEQUENCE_VERIFICATION.value, is_trick)
        return GeneratedQuestion(
            video_name=entry.get("video_name", "unknown"),
            question_type=QuestionType.SEQUENCE_VERIFICATION.value,
            prompt=prompt,
            answers=answers,
            correct_answer=correct_answer,
            correct_index=correct_index,
            is_trick=is_trick,
            option_hardness=option_hardness,
        )
