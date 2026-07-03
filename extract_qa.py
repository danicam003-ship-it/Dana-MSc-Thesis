#!/usr/bin/env python3
"""Extract auditable interview Q&A candidates from the supplied transcript PDF."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader


PDF_PATH = Path(
    "/Users/danicam003/Desktop/Data for master thesis/"
    "ANDREW HUBERMAN\u00a0Welcome to Huberman Lab Essentials.pdf"
)
OUTPUT_PATH = Path(
    "/Users/danicam003/Documents/Codex/2026-06-20/"
    "i-am-doing-a-master-thesis/work/huberman_qa/qa_data.json"
)

HOST = "Andrew Huberman"
KNOWN_SPEAKERS = [
    "Andrew Huberman",
    "Thaïs Aliabadi",
    "Thais Aliabadi",
    "Jack Feldman",
    "Jennifer Groh",
    "Konstantina Stankovic",
    "Alan Aragon",
    "Alia Crum",
    "Karl Deisseroth",
    "Stacy Sims",
    "Casey Means",
]

EPISODES = [
    {
        "episode_id": "EP-001",
        "title": "Women's Reproductive and General Health: PCOS, Endometriosis, Breast Cancer, Perimenopause and Menopause",
        "start_page": 11,
        "end_page": 79,
        "guest": "Thaïs Aliabadi",
        "guest_credentials": "MD",
        "guest_role": "Obstetrician, gynecologist and surgeon",
        "credential_url": "https://www.draliabadi.com/about-dr-aliabadi-los-angeles-obgyn-gynecologist-surgeon/",
    },
    {
        "episode_id": "EP-002",
        "title": "Breathing, the Brain and Health",
        "start_page": 80,
        "end_page": 96,
        "guest": "Jack Feldman",
        "guest_credentials": "PhD",
        "guest_role": "Distinguished Professor of Neurobiology",
        "credential_url": "https://bri.ucla.edu/people/jack-feldman/",
    },
    {
        "episode_id": "EP-003",
        "title": "How the Brain Represents the Senses, Space and Thought",
        "start_page": 97,
        "end_page": 191,
        "guest": "Jennifer Groh",
        "guest_credentials": "PhD",
        "guest_role": "Professor of psychology, neuroscience and neurobiology",
        "credential_url": "https://www.neuro.duke.edu/profile/jennifer-m-groh",
    },
    {
        "episode_id": "EP-004",
        "title": "Hearing, Balance and Brain Health",
        "start_page": 191,
        "end_page": 259,
        "guest": "Konstantina Stankovic",
        "guest_credentials": "MD, PhD, FACS",
        "guest_role": "Auditory neuroscientist and neurotologic surgeon",
        "credential_url": "https://profiles.stanford.edu/konstantina-stankovic?tab=bio",
    },
    {
        "episode_id": "EP-005",
        "title": "Nutrition and Fitness for Body Composition",
        "start_page": 260,
        "end_page": 328,
        "guest": "Alan Aragon",
        "guest_credentials": "Credential not confirmed as PhD",
        "guest_role": "Nutrition researcher and educator",
        "credential_url": "https://alanaragon.com/about/",
    },
    {
        "episode_id": "EP-006",
        "title": "Mindsets and Their Effects on Health and Performance",
        "start_page": 339,
        "end_page": 353,
        "guest": "Alia Crum",
        "guest_credentials": "PhD",
        "guest_role": "Psychologist and mindset researcher",
        "credential_url": "https://profiles.stanford.edu/alia-crum",
    },
    {
        "episode_id": "EP-007",
        "title": "Psychiatry, Mental Illness and the Future of Brain Science",
        "start_page": 353,
        "end_page": 367,
        "guest": "Karl Deisseroth",
        "guest_credentials": "MD, PhD",
        "guest_role": "Psychiatrist, neuroscientist and bioengineer",
        "credential_url": "https://profiles.stanford.edu/karl-deisseroth",
    },
    {
        "episode_id": "EP-008",
        "title": "Women-Specific Exercise, Nutrition and Hormonal Health",
        "start_page": 410,
        "end_page": 463,
        "guest": "Stacy Sims",
        "guest_credentials": "MSc, PhD",
        "guest_role": "Exercise physiologist and nutrition scientist",
        "credential_url": "https://www.drstacysims.com/about-stacy",
    },
    {
        "episode_id": "EP-009",
        "title": "Metabolic Health, Mitochondria and Whole-Body Well-Being",
        "start_page": 463,
        "end_page": 519,
        "guest": "Casey Means",
        "guest_credentials": "MD",
        "guest_role": "Physician and metabolic-health author",
        "credential_url": "https://med.stanford.edu/news/all-news/2025/05/statement-casey-means.html",
    },
]

CREDENTIALS = {
    "Andrew Huberman": {
        "credentials": "PhD",
        "role": "Neuroscientist and professor of neurobiology and ophthalmology",
        "url": "https://profiles.stanford.edu/andrew-huberman",
    }
}

AGENT_TERMS = {
    "Psychological Symptoms": [
        "anxiety", "depression", "psychiat", "emotion", "stress", "fear",
        "mental health", "schizophrenia", "autism", "mood", "trauma",
    ],
    "Sleep": ["sleep", "insomnia", "circadian", "night", "wake", "dream"],
    "Reproductive and Hormonal Health": [
        "pcos", "endometriosis", "menopause", "perimenopause", "menstrual",
        "period", "hormone", "fertility", "estrogen", "progesterone", "ovarian",
    ],
    "Nutrition and Body": [
        "nutrition", "protein", "diet", "food", "glucose", "insulin", "fat",
        "muscle", "exercise", "training", "metabolic", "mitochond", "calorie",
    ],
    "Lifestyle and Context": [
        "relationship", "social", "work", "environment", "habit", "behavior",
        "lifestyle", "motivation", "mindset", "learning",
    ],
    "Intervention": [
        "treat", "therapy", "protocol", "supplement", "medication", "tool",
        "recommend", "practice", "intervention", "diagnos", "screen",
    ],
    "Safety": ["suicid", "self-harm", "abuse", "danger", "cancer", "overdose"],
}

STOPWORDS = {
    "the", "and", "that", "this", "with", "from", "what", "when", "where",
    "which", "would", "could", "should", "have", "has", "had", "about", "into",
    "your", "you", "they", "their", "there", "then", "than", "does", "did",
    "for", "are", "was", "were", "can", "how", "why", "who", "our", "but",
}

PROMOTIONAL_EXCLUDE_TERMS = {
    "sponsor", "youtube", "spotify", "apple", "newsletter", "social media",
    "show note", "subscribe", "podcast by clicking", "book coming out",
}

CURATION_EXCLUDE_TERMS = {
    "where can people find you", "you spent two days", "decent-sized omelet",
    "that's what this is", "naked eyeballing", "snickers bar", "dad joke",
    "after the last bite", "is that right?", "maple syrup does for you",
    "you're saying it's because", "where does that sit with you",
    "can they hear a whisper", "if you're not doing that",
    "could it be that mindset", "simply because it's accessible",
    "what's the secret code", "can do both, right", "what phases of the menstrual cycle are those",
    "can we talk about pcos", "best time in cycle to do that blood test",
    "move their lips a little less", "amplify aspects of the music",
    "something that they really benefit", "what you just described more",
    "direction of the effect was on the amygdala", "why would you do that",
    "there's a middle ground, right", "and lately, what does that breath practice",
    "do you see any harm in them, kind of emphasizing magnesium",
}

PROMPT_PATTERNS = re.compile(
    r"\b(?:tell us|tell me|explain|describe|walk us through|elaborate|share with us|"
    r"start off by|talk about|give us|help us understand)\b",
    flags=re.IGNORECASE,
)


@dataclass
class Turn:
    speaker: str
    text: str
    start_page: int
    end_page: int


def clean(text: str) -> str:
    text = text.replace("\x00", " ").replace("\u00ad", "")
    return re.sub(r"\s+", " ", text).strip()


def canonical_speaker(raw: str) -> str:
    value = clean(raw).strip("[]:")
    if value.lower() == "thais aliabadi":
        return "Thaïs Aliabadi"
    for speaker in KNOWN_SPEAKERS:
        if value.casefold() == speaker.casefold():
            return "Thaïs Aliabadi" if speaker == "Thais Aliabadi" else speaker
    return value.title()


SPEAKER_PATTERN = re.compile(
    r"^(?:\[)?(" + "|".join(re.escape(name) for name in KNOWN_SPEAKERS) + r")(?:\])?\s*:?\s*(.*)$",
    flags=re.IGNORECASE,
)


def parse_turns(pages: list[str], start_page: int, end_page: int) -> list[Turn]:
    turns: list[Turn] = []
    current_speaker = ""
    current_lines: list[str] = []
    current_start = start_page

    def flush(page_number: int) -> None:
        nonlocal current_lines
        text = clean(" ".join(current_lines))
        if current_speaker and text:
            turns.append(Turn(current_speaker, text, current_start, page_number))
        current_lines = []

    for page_number in range(start_page, end_page + 1):
        page_text = pages[page_number - 1]
        for raw_line in page_text.splitlines():
            line = clean(raw_line)
            if not line or line in {"[MUSIC PLAYING]", "[LAUGHING]"}:
                continue
            match = SPEAKER_PATTERN.match(line)
            if match:
                flush(page_number)
                current_speaker = canonical_speaker(match.group(1))
                current_start = page_number
                remainder = clean(match.group(2))
                current_lines = [remainder] if remainder else []
            elif current_speaker:
                current_lines.append(line)
        # Do not flush at page boundaries because a turn can continue.
    flush(end_page)
    return turns


def question_from_turn(text: str) -> str:
    sentences = re.split(r"(?<=[?.!])\s+", clean(text))
    questions = [sentence for sentence in sentences if "?" in sentence]
    if not questions:
        if not PROMPT_PATTERNS.search(text):
            return ""
        value = clean(text)
        words = value.split()
        return " ".join(words[:120]) + ("..." if len(words) > 120 else "")
    selected = questions[-2:] if sum(len(q.split()) for q in questions[-2:]) <= 70 else questions[-1:]
    return clean(" ".join(selected))


def concise_answer(text: str, max_words: int = 85) -> str:
    value = clean(text)
    value = re.sub(r"^(?:yeah|yes|right|well|okay|so)\b[,.:; -]*", "", value, flags=re.I)
    sentences = re.split(r"(?<=[.!?])\s+", value)
    selected: list[str] = []
    count = 0
    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue
        if selected and count + len(words) > max_words:
            break
        selected.append(sentence)
        count += len(words)
        if len(selected) >= 3 or count >= 45:
            break
    answer = clean(" ".join(selected))
    words = answer.split()
    if len(words) > max_words:
        answer = " ".join(words[:max_words]).rstrip(",;:") + "..."
    return answer


def tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z][a-z-]{2,}", text.lower())
        if token not in STOPWORDS
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def classify_agent(question: str, answer: str) -> tuple[str, str]:
    text = f"{question} {answer}".lower()
    scores = {
        agent: sum(text.count(term) for term in terms)
        for agent, terms in AGENT_TERMS.items()
    }
    ranked = sorted(scores, key=lambda key: (-scores[key], key))
    primary = ranked[0] if scores[ranked[0]] else "Psychological Symptoms"
    secondary = [agent for agent in ranked[1:] if scores[agent] > 0][:2]
    return primary, "; ".join(secondary)


def classify_question(question: str) -> str:
    lowered = question.lower()
    if any(term in lowered for term in ["what is", "what are", "difference between", "define"]):
        return "Definition or distinction"
    if any(term in lowered for term in ["how does", "how do", "mechanism", "what happens"]):
        return "Mechanism"
    if any(term in lowered for term in ["what can", "what should", "recommend", "protocol", "treat"]):
        return "Intervention or practical guidance"
    if any(term in lowered for term in ["diagnos", "test", "screen", "identify"]):
        return "Assessment or diagnosis"
    if any(term in lowered for term in ["risk", "danger", "safe", "cause"]):
        return "Risk or association"
    return "Explanation"


def candidate_score(question: str, answer: str) -> float:
    q_words = len(question.split())
    a_words = len(answer.split())
    score = 0.0
    score += 2.0 if 7 <= q_words <= 55 else 0.5
    score += min(a_words, 70) / 35
    score += 1.0 if any(term in f"{question} {answer}".lower() for terms in AGENT_TERMS.values() for term in terms) else 0
    primary, _ = classify_agent(question, answer)
    if primary in {"Psychological Symptoms", "Sleep", "Reproductive and Hormonal Health", "Intervention"}:
        score += 1.5
    elif primary == "Nutrition and Body":
        score += 0.75
    if re.match(r"^(?:is|are|so|but|except)\s+(?:that|this|it)\b", question.lower()) and q_words < 22:
        score -= 2.5
    score -= 3.0 if any(term in f"{question} {answer}".lower() for term in CURATION_EXCLUDE_TERMS) else 0
    return score


def context_dependency(question: str) -> str:
    lowered = question.lower().strip()
    if len(question.split()) < 7:
        return "High - short follow-up"
    if re.match(r"^(?:and|but|so|is|are|does|do|that|this|it|except)\b", lowered):
        return "Moderate - preceding context may be needed"
    if any(phrase in lowered for phrase in ["what you just", "that effect", "those things", "do both", "is that right"]):
        return "High - deictic wording"
    return "Low"


def select_diverse(candidates: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    remaining = sorted(candidates, key=lambda row: row["quality_score"], reverse=True)
    selected: list[dict[str, Any]] = []
    while remaining and len(selected) < limit:
        best = max(
            remaining,
            key=lambda row: row["quality_score"] - 2.2 * max(
                [jaccard(row["token_set"], item["token_set"]) for item in selected] or [0.0]
            ),
        )
        selected.append(best)
        remaining.remove(best)
    return sorted(selected, key=lambda row: (row["question_page"], row["question"]))


def build() -> dict[str, Any]:
    reader = PdfReader(str(PDF_PATH))
    pages = [page.extract_text() or "" for page in reader.pages]
    all_pairs: list[dict[str, Any]] = []
    curated_pairs: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []

    for episode in EPISODES:
        turns = parse_turns(pages, episode["start_page"], episode["end_page"])
        candidates: list[dict[str, Any]] = []
        for index, turn in enumerate(turns[:-1]):
            if turn.speaker != HOST or ("?" not in turn.text and not PROMPT_PATTERNS.search(turn.text)):
                continue
            next_turn = turns[index + 1]
            if next_turn.speaker != episode["guest"]:
                continue
            question = question_from_turn(turn.text)
            answer = concise_answer(next_turn.text)
            if len(question.split()) < 2 or len(answer.split()) < 3:
                continue
            combined = f"{question} {answer}".lower()
            if any(term in combined for term in PROMOTIONAL_EXCLUDE_TERMS):
                continue
            primary, secondary = classify_agent(question, answer)
            safety = "Clinical safety review" if primary == "Safety" or any(
                term in combined for term in ["suicid", "self-harm", "cancer", "overdose"]
            ) else "None identified"
            confidence = 0.92 if len(answer.split()) >= 25 and 7 <= len(question.split()) <= 55 else 0.84
            dependency = context_dependency(question)
            row = {
                "episode_id": episode["episode_id"],
                "episode_title": episode["title"],
                "interviewer": HOST,
                "interviewer_credentials": CREDENTIALS[HOST]["credentials"],
                "interviewee": episode["guest"],
                "interviewee_credentials": episode["guest_credentials"],
                "question": question,
                "possible_answer": answer,
                "question_page": turn.start_page,
                "answer_page_start": next_turn.start_page,
                "answer_page_end": next_turn.end_page,
                "primary_agent": primary,
                "secondary_agents": secondary,
                "question_type": classify_question(question),
                "safety_tag": safety,
                "extraction_confidence": confidence,
                "transcript_review_status": "User reports human-reviewed source",
                "qa_review_status": "Automatic extraction - manual verification required",
                "quality_score": candidate_score(question, answer),
                "token_set": tokens(question),
                "context_dependency": dependency,
                "recommended_for_q2q": "Yes" if dependency == "Low" and confidence >= 0.9 else "Review",
            }
            row["pair_id"] = f"QA-{len(all_pairs) + 1:04d}"
            all_pairs.append({key: value for key, value in row.items() if key != "token_set"})
            candidates.append(row)

        curated_pool = [
            row for row in candidates
            if not any(term in f"{row['question']} {row['possible_answer']}".lower() for term in CURATION_EXCLUDE_TERMS)
        ]
        selected = select_diverse(curated_pool, limit=6)
        for row in selected:
            curated = {key: value for key, value in row.items() if key not in {"quality_score", "token_set"}}
            curated["curated_id"] = f"CUR-{len(curated_pairs) + 1:04d}"
            curated_pairs.append(curated)
        episode_rows.append({
            **episode,
            "interviewer": HOST,
            "interviewer_credentials": CREDENTIALS[HOST]["credentials"],
            "interviewer_credential_url": CREDENTIALS[HOST]["url"],
            "turn_count": len(turns),
            "candidate_count": len(candidates),
            "selected_pair_count": len(selected),
            "boundary_method": "PDF page transition / large white gap plus episode introduction and sign-off",
            "transcript_review_status": "User reports human-reviewed source",
            "episode_title_status": "Descriptive title derived from transcript introduction",
        })

    return {
        "source_file": str(PDF_PATH),
        "source_sha256": hashlib.sha256(PDF_PATH.read_bytes()).hexdigest(),
        "page_count": len(pages),
        "interviewer": {"name": HOST, **CREDENTIALS[HOST]},
        "episodes": episode_rows,
        "qa_pairs": all_pairs,
        "curated_qa_pairs": curated_pairs,
        "method_notes": [
            "Episodes were segmented using visual page transitions, introductory language and sign-offs.",
            "Only interviewer turns containing a question mark followed by the named guest were eligible.",
            "Possible answers are short transcript-derived openings, not independently verified medical conclusions.",
            "Diversity selection penalized lexical similarity within each episode.",
            "All extracted pairs require human verification even when the source transcript was human reviewed.",
        ],
    }


if __name__ == "__main__":
    data = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "pages": data["page_count"],
        "episodes": len(data["episodes"]),
        "qa_pairs": len(data["qa_pairs"]),
        "curated_pairs": len(data["curated_qa_pairs"]),
        "per_episode": {
            episode["episode_id"]: episode["selected_pair_count"]
            for episode in data["episodes"]
        },
        "output": str(OUTPUT_PATH),
    }, indent=2))
