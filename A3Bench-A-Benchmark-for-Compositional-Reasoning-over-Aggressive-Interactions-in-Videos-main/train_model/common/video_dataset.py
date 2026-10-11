"""Multimodal video dataset for InternVL2.5 fine-tuning.

Every sample returns a dict consumable by InternVLChatModel.forward:

    {
      "pixel_values":    FloatTensor[F, 3, 448, 448],   # F frames
      "input_ids":       LongTensor[L],
      "attention_mask":  LongTensor[L],
      "image_flags":     LongTensor[F],                 # 1 per usable frame
      "labels":          LongTensor[L],                 # -100 outside the answer span
    }

Prompt layout (internvl2_5 conversation template):

    <|im_start|>system
    {system_message}<|im_end|>
    <|im_start|>user
    Frame 1: <image>
    Frame 2: <image>
    ...
    Frame F: <image>
    {video_context_as_question_guidance}
    Question: {prompt}<|im_end|>
    <|im_start|>assistant
    {answer}<|im_end|>

Each `<image>` is expanded into `<img>` + `<IMG_CONTEXT>` * num_image_token + `</img>`
so the model sees a fixed number of visual tokens per frame at the correct positions.

Label masking: we tokenize the prompt-only prefix and the full sequence separately
and mask everything before `len(prompt_ids)` to -100 so loss is computed only on
the assistant's answer tokens (standard SFT with chat template).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

IMG_START_TOKEN = "<img>"
IMG_END_TOKEN = "</img>"
IMG_CONTEXT_TOKEN = "<IMG_CONTEXT>"


def build_image_transform(image_size: int) -> transforms.Compose:
    return transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def _frames_cached(frames_dir: Path, video_name: str, n_frames: int) -> bool:

    stem = Path(video_name).stem
    d = frames_dir / stem
    return all((d / f"frame_{i:02d}.jpg").exists() for i in range(n_frames))


def _filter_cached(examples: list, frames_dir: Path, n_frames: int,
                   source: str = "") -> list:

    kept = [ex for ex in examples if _frames_cached(frames_dir, ex["video_name"],
                                                    n_frames)]
    dropped = len(examples) - len(kept)
    if dropped:
        print(
            f"  [video_dataset] {source}: kept {len(kept)}/{len(examples)} "
            f"examples; dropped {dropped} whose frames aren't cached.",
            flush=True,
        )
    return kept


def _validate_mcq_consistency(examples: list, source: str = "") -> None:

    for i, ex in enumerate(examples):
        answers = ex.get("all_answers")
        if not answers:
            continue
        idx = ex.get("correct_index", -1)
        if idx < 0 or idx >= len(answers):
            raise ValueError(
                f"MCQ consistency violation in {source!r} at index {i} "
                f"(video={ex.get('video_name')!r}): correct_index={idx} "
                f"out of range for {len(answers)} options"
            )
        if answers[idx] != ex["correct_answer"]:
            raise ValueError(
                f"MCQ consistency violation in {source!r} at index {i} "
                f"(video={ex.get('video_name')!r}): "
                f"all_answers[{idx}]={answers[idx]!r} != "
                f"correct_answer={ex['correct_answer']!r}"
            )


def _load_frames(frames_dir: Path, video_name: str, n_frames: int,
                 transform: transforms.Compose) -> torch.Tensor:

    stem = Path(video_name).stem
    video_frames_dir = frames_dir / stem
    pixels = []
    for i in range(n_frames):
        img_path = video_frames_dir / f"frame_{i:02d}.jpg"
        with Image.open(img_path) as img:
            img = img.convert("RGB")
            pixels.append(transform(img))
    return torch.stack(pixels)


def _expand_image_tokens(text: str, num_patches_list: list[int],
                         num_image_token: int) -> str:

    for num_patches in num_patches_list:
        image_tokens = (
            IMG_START_TOKEN
            + IMG_CONTEXT_TOKEN * num_image_token * num_patches
            + IMG_END_TOKEN
        )
        text = text.replace("<image>", image_tokens, 1)
    return text


def format_chat_prompt(system_message: str, user_content: str,
                       assistant_content: str | None,
                       role_user: str = "<|im_start|>user\n",
                       role_assistant: str = "<|im_start|>assistant\n",
                       sep: str = "<|im_end|>\n") -> str:

    system = f"<|im_start|>system\n{system_message}{sep}" if system_message else ""
    user = f"{role_user}{user_content}{sep}"
    if assistant_content is None:
        assistant = role_assistant
    else:
        assistant = f"{role_assistant}{assistant_content}{sep}"
    return system + user + assistant


def build_user_content(frames_per_video: int, question: str, options: list[str] = None) -> str:

    frame_lines = "\n".join(f"Frame {i+1}: <image>" for i in range(frames_per_video))
    content = f"{frame_lines}\n\nQuestion: {question}"
    if options:
        content += "\nOptions:"
        for i, opt in enumerate(options):
            letter = chr(ord('A') + i)
            content += f"\n{letter}) {opt}"
    return content


@dataclass
class MultimodalExample:
    pixel_values: torch.Tensor
    input_ids: torch.Tensor
    attention_mask: torch.Tensor
    image_flags: torch.Tensor
    labels: torch.Tensor


class VideoSFTDataset(Dataset):
    """Dataset for Phase 1 SFT and Phase 3 CoT SFT.

    Each example is expected to have:
        video_name, video_context, prompt, correct_answer
    Optional:
        reasoning (prepended to answer for CoT training).
    """

    def __init__(self, data_path: str, tokenizer, config: dict,
                 num_image_token: int, system_message: str = "",
                 is_train: bool = True):
        with open(data_path, encoding="utf-8") as f:
            raw = json.load(f)

        examples = [self._normalize(ex) for ex in raw]
        self.tokenizer = tokenizer
        self.cfg = config
        self.num_image_token = num_image_token
        self.system_message = system_message
        self.is_train = is_train


\


        self.randomize_options = bool(
            config.get("data", {}).get("randomize_options", False)
        )
        self.transform = build_image_transform(config["video"]["image_size"])
        self.frames_dir = Path(config["video"]["frames_dir"])
        self.n_frames = int(config["video"]["frames_per_video"])
        self.num_patches = int(config["video"].get("num_patches_per_frame", 1))
        self.max_length = int(config["tokenization"]["max_length"])


        self.examples = _filter_cached(examples, self.frames_dir, self.n_frames,
                                       source=data_path)


        # bare-text training targets with no letter prefix. Crash loudly now
        # rather than corrupt training silently.
        _validate_mcq_consistency(self.examples, source=data_path)

    @staticmethod
    def _normalize(ex: dict) -> dict:


        if "chosen" in ex and isinstance(ex["chosen"], dict):
            chosen = ex["chosen"]
            return {
                "video_name": ex.get("video_name", ""),
                "video_context": ex.get("video_context", ""),
                "prompt": ex.get("prompt", ""),
                "correct_answer": chosen.get("answer", ""),
                "reasoning": chosen.get("reasoning", ""),
                "all_answers": ex.get("all_answers", []),
                "correct_index": ex.get("correct_index", -1),
            }
        return {
            "video_name": ex.get("video_name", ""),
            "video_context": ex.get("video_context", ""),
            "prompt": ex.get("prompt", ""),
            "correct_answer": ex.get("correct_answer", ""),
            "reasoning": ex.get("reasoning", ""),
            "all_answers": ex.get("all_answers", []),
            "correct_index": ex.get("correct_index", -1),
        }

    def __len__(self) -> int:
        return len(self.examples)

    def _shuffle_options(self, ex: dict) -> tuple[list[str] | None, int]:

        answers = ex.get("all_answers")
        idx = ex.get("correct_index", -1)
        if not answers or not self.randomize_options or not self.is_train:
            return answers, idx
        perm = list(range(len(answers)))
        random.shuffle(perm)
        shuffled = [answers[i] for i in perm]
        new_idx = perm.index(idx)
        return shuffled, new_idx

    def _build_answer(self, ex: dict, answers: list[str] | None, correct_idx: int) -> str:

        if answers:
            if correct_idx < 0 or correct_idx >= len(answers):
                raise ValueError(
                    f"MCQ consistency violation in {ex.get('video_name')!r}: "
                    f"correct_index={correct_idx} / answers len={len(answers)}"
                )
            if answers[correct_idx] != ex["correct_answer"]:
                raise ValueError(
                    f"MCQ consistency violation in {ex.get('video_name')!r}: "
                    f"answers[{correct_idx}]={answers[correct_idx]!r} != "
                    f"correct_answer={ex['correct_answer']!r}"
                )
            letter = chr(ord("A") + correct_idx)
            answer_text = f"{letter}) {ex['correct_answer']}"
        else:
            answer_text = ex["correct_answer"]
        if ex.get("reasoning"):
            return f"Reasoning:\n{ex['reasoning']}\n\nAnswer: {answer_text}"
        return answer_text

    def __getitem__(self, idx: int) -> dict:
        ex = self.examples[idx]
        pixel_values = _load_frames(self.frames_dir, ex["video_name"],
                                    self.n_frames, self.transform)

        shuffled_answers, correct_idx = self._shuffle_options(ex)
        user_content = build_user_content(self.n_frames, ex["prompt"], shuffled_answers)

        num_patches_list = [self.num_patches] * self.n_frames
        user_content_expanded = _expand_image_tokens(
            user_content, num_patches_list, self.num_image_token,
        )

        prompt_text = format_chat_prompt(self.system_message, user_content_expanded,
                                         assistant_content=None)
        full_text = format_chat_prompt(self.system_message, user_content_expanded,
                                       assistant_content=self._build_answer(ex, shuffled_answers, correct_idx))

        prompt_ids = self.tokenizer(prompt_text, add_special_tokens=False,
                                    return_tensors="pt")["input_ids"][0]
        full_enc = self.tokenizer(full_text, add_special_tokens=False,
                                  max_length=self.max_length, truncation=True,
                                  padding="max_length", return_tensors="pt")
        input_ids = full_enc["input_ids"][0]
        attention_mask = full_enc["attention_mask"][0]

\

        # so pathological prompts don't silently lose their answer tokens.
        if int(attention_mask.sum()) == self.max_length:
            eos_id = self.tokenizer.eos_token_id
            if eos_id is None or int(input_ids[-1]) != int(eos_id):
                print(
                    f"  [video_dataset] truncated: video={ex.get('video_name')!r} "
                    f"(prompt+answer filled max_length={self.max_length})",
                    flush=True,
                )


        labels = input_ids.clone()
        prompt_len = min(prompt_ids.numel(), input_ids.numel())
        labels[:prompt_len] = -100
        labels[attention_mask == 0] = -100

        image_flags = torch.ones(self.n_frames * self.num_patches, dtype=torch.long)

        return {
            "pixel_values": pixel_values,
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "image_flags": image_flags,
            "labels": labels,
        }


class VideoDPOPairDataset(Dataset):
    """Dataset for Phase 5 ADPO preference pairs.

    Each sample returns two full InternVL-ready sequences (chosen, rejected)
    plus the shared pixel_values.
    """

    def __init__(self, pairs_path: str, tokenizer, config: dict,
                 num_image_token: int, system_message: str = "",
                 is_train: bool = True):
        with open(pairs_path, encoding="utf-8") as f:
            raw = json.load(f)
        pairs = [p for p in raw if p.get("rejected")]
        self.tokenizer = tokenizer
        self.cfg = config
        self.num_image_token = num_image_token
        self.system_message = system_message
        self.is_train = is_train

        # DPO shuffle MUST apply the same permutation to chosen and rejected
        # so their prompts remain byte-identical -- otherwise DPO trains on

        self.randomize_options = bool(
            config.get("data", {}).get("randomize_options", False)
        )
        self.transform = build_image_transform(config["video"]["image_size"])
        self.frames_dir = Path(config["video"]["frames_dir"])
        self.n_frames = int(config["video"]["frames_per_video"])
        self.num_patches = int(config["video"].get("num_patches_per_frame", 1))
        self.max_length = int(config["tokenization"]["max_length"])
        self.pairs = _filter_cached(pairs, self.frames_dir, self.n_frames,
                                    source=pairs_path)

    def __len__(self) -> int:
        return len(self.pairs)

    def _encode_response(self, prompt: str, all_answers: list[str] | None,
                         answer_text: str) -> dict:
        user_content = build_user_content(self.n_frames, prompt, all_answers)
        num_patches_list = [self.num_patches] * self.n_frames
        user_content_expanded = _expand_image_tokens(
            user_content, num_patches_list, self.num_image_token,
        )
        prompt_text = format_chat_prompt(self.system_message, user_content_expanded,
                                         assistant_content=None)
        full_text = format_chat_prompt(self.system_message, user_content_expanded,
                                       assistant_content=answer_text)

        prompt_ids = self.tokenizer(prompt_text, add_special_tokens=False,
                                    return_tensors="pt")["input_ids"][0]
        full_enc = self.tokenizer(full_text, add_special_tokens=False,
                                  max_length=self.max_length, truncation=True,
                                  padding="max_length", return_tensors="pt")
        input_ids = full_enc["input_ids"][0]
        attention_mask = full_enc["attention_mask"][0]


        response_mask = torch.zeros_like(input_ids, dtype=torch.long)
        prompt_len = min(prompt_ids.numel(), input_ids.numel())
        response_mask[prompt_len:] = 1
        response_mask = response_mask * attention_mask
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "response_mask": response_mask,
        }

    def _shuffle_pair(self, pair: dict) -> tuple[list[str] | None, str, str]:

        all_answers = pair.get("all_answers")
        correct_index = pair.get("correct_index", -1)
        chosen_pre = pair["chosen"]["answer"]
        rejected_pre = pair["rejected"][0]["answer"]

        \
        if not self.randomize_options or not self.is_train or not all_answers:
            return all_answers, chosen_pre, rejected_pre


        rej0 = pair["rejected"][0]
        if "index" not in rej0 or "text" not in rej0 or correct_index < 0:
            return all_answers, chosen_pre, rejected_pre

        perm = list(range(len(all_answers)))
        random.shuffle(perm)
        shuffled = [all_answers[i] for i in perm]
        new_correct_idx = perm.index(correct_index)
        new_rejected_idx = perm.index(rej0["index"])

        correct_letter = chr(ord("A") + new_correct_idx)
        rejected_letter = chr(ord("A") + new_rejected_idx)
        correct_text = all_answers[correct_index]
        rejected_text = rej0["text"]
        chosen_ans = f"{correct_letter}) {correct_text}"
        rejected_ans = f"{rejected_letter}) {rejected_text}"
        return shuffled, chosen_ans, rejected_ans

    def __getitem__(self, idx: int) -> dict:
        pair = self.pairs[idx]
        pixel_values = _load_frames(self.frames_dir, pair["video_name"],
                                    self.n_frames, self.transform)

        shuffled_answers, chosen_ans, rejected_ans = self._shuffle_pair(pair)
        if pair["chosen"].get("reasoning"):
            chosen_ans = f"Reasoning:\n{pair['chosen']['reasoning']}\n\nAnswer: {chosen_ans}"

        chosen = self._encode_response(pair["prompt"], shuffled_answers, chosen_ans)
        rejected = self._encode_response(pair["prompt"], shuffled_answers, rejected_ans)
        image_flags = torch.ones(self.n_frames * self.num_patches, dtype=torch.long)

        return {
            "pixel_values": pixel_values,
            "chosen_input_ids":      chosen["input_ids"],
            "chosen_attention_mask": chosen["attention_mask"],
            "chosen_response_mask":  chosen["response_mask"],
            "rejected_input_ids":      rejected["input_ids"],
            "rejected_attention_mask": rejected["attention_mask"],
            "rejected_response_mask":  rejected["response_mask"],
            "image_flags": image_flags,
        }


def register_image_context_token(tokenizer) -> int:

    token_id = tokenizer.convert_tokens_to_ids(IMG_CONTEXT_TOKEN)
    if token_id is None or token_id == tokenizer.unk_token_id:
        \
        tokenizer.add_special_tokens({"additional_special_tokens": [IMG_CONTEXT_TOKEN]})
        token_id = tokenizer.convert_tokens_to_ids(IMG_CONTEXT_TOKEN)
    return int(token_id)


def collate_sft(batch: list[dict]) -> dict[str, torch.Tensor]:

    return {
        "pixel_values": torch.cat([b["pixel_values"] for b in batch], dim=0),
        "input_ids": torch.stack([b["input_ids"] for b in batch]),
        "attention_mask": torch.stack([b["attention_mask"] for b in batch]),
        "image_flags": torch.cat([b["image_flags"] for b in batch], dim=0),
        "labels": torch.stack([b["labels"] for b in batch]),
    }


def collate_dpo(batch: list[dict]) -> dict[str, torch.Tensor]:
    return {
        "pixel_values": torch.cat([b["pixel_values"] for b in batch], dim=0),
        "image_flags": torch.cat([b["image_flags"] for b in batch], dim=0),
        "chosen_input_ids":      torch.stack([b["chosen_input_ids"] for b in batch]),
        "chosen_attention_mask": torch.stack([b["chosen_attention_mask"] for b in batch]),
        "chosen_response_mask":  torch.stack([b["chosen_response_mask"] for b in batch]),
        "rejected_input_ids":      torch.stack([b["rejected_input_ids"] for b in batch]),
        "rejected_attention_mask": torch.stack([b["rejected_attention_mask"] for b in batch]),
        "rejected_response_mask":  torch.stack([b["rejected_response_mask"] for b in batch]),
    }
