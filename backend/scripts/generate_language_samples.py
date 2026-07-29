"""언어별 추천 품질 검증용 샘플 생성기 (이슈 #11).

각 언어의 대표 감정 쿼리 6종으로 실제 /recommend 파이프라인(쿼리 확장 →
검색 → LLM 선별 → 코멘트 생성)을 돌려 결과를 JSON 으로 저장한다.
**언어를 새로 켜기 전에** 이 스크립트로 샘플을 만들고, LLM 저지(에이전트)로
언어 순도·구절-코멘트 정합·목회적 어조를 판정하는 것이 검증 절차다.

    python scripts/generate_language_samples.py --out /tmp/lang_samples [--lang en]

요구: OPENAI_API_KEY(backend/.env), 로컬 언어 데이터(data/langs/), ML venv.
로컬에서 전 언어를 켠 data/language_config.json 이 있어야 한다(gitignore 됨).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# `python scripts/…` 로 실행해도 backend 루트의 app.py 를 import 할 수 있게 한다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 언어별 대표 감정 쿼리 — ①지침/위로 ②미래 불안 ③상실/슬픔 ④외로움 ⑤죄책감 ⑥감사
MOODS = {
    "en": [
        "I'm so exhausted lately, I just need some comfort",
        "I'm anxious about my future and can't sleep",
        "I lost someone I love and the grief won't go away",
        "I feel completely alone, like nobody understands me",
        "I keep failing and I feel so guilty before God",
        "My heart is full of gratitude today and I want to give thanks",
    ],
    "es": [
        "Estoy agotado últimamente, solo necesito un poco de consuelo",
        "Estoy ansioso por mi futuro y no puedo dormir",
        "Perdí a alguien que amo y el dolor no se va",
        "Me siento completamente solo, como si nadie me entendiera",
        "Sigo fallando y me siento muy culpable delante de Dios",
        "Hoy mi corazón está lleno de gratitud y quiero dar gracias",
    ],
    "pt": [
        "Estou tão cansado ultimamente, só preciso de um pouco de consolo",
        "Estou ansioso com o meu futuro e não consigo dormir",
        "Perdi alguém que amo e a dor não passa",
        "Sinto-me completamente sozinho, como se ninguém me entendesse",
        "Continuo falhando e me sinto muito culpado diante de Deus",
        "Hoje meu coração está cheio de gratidão e quero agradecer",
    ],
    "de": [
        "Ich bin in letzter Zeit so erschöpft, ich brauche einfach Trost",
        "Ich habe Angst vor meiner Zukunft und kann nicht schlafen",
        "Ich habe einen geliebten Menschen verloren und die Trauer vergeht nicht",
        "Ich fühle mich völlig allein, als würde mich niemand verstehen",
        "Ich versage immer wieder und fühle mich so schuldig vor Gott",
        "Mein Herz ist heute voller Dankbarkeit und ich möchte danken",
    ],
    "fr": [
        "Je suis épuisé ces derniers temps, j'ai juste besoin de réconfort",
        "Je suis anxieux pour mon avenir et je n'arrive pas à dormir",
        "J'ai perdu un être cher et le chagrin ne s'en va pas",
        "Je me sens complètement seul, comme si personne ne me comprenait",
        "J'échoue sans cesse et je me sens si coupable devant Dieu",
        "Mon cœur est plein de gratitude aujourd'hui et je veux rendre grâce",
    ],
    "it": [
        "Ultimamente sono esausto, ho solo bisogno di un po' di conforto",
        "Sono in ansia per il mio futuro e non riesco a dormire",
        "Ho perso una persona cara e il dolore non passa",
        "Mi sento completamente solo, come se nessuno mi capisse",
        "Continuo a sbagliare e mi sento così in colpa davanti a Dio",
        "Oggi il mio cuore è pieno di gratitudine e voglio ringraziare",
    ],
    "pl": [
        "Ostatnio jestem wyczerpany, potrzebuję po prostu pocieszenia",
        "Boję się o swoją przyszłość i nie mogę spać",
        "Straciłem kogoś bliskiego i żal nie mija",
        "Czuję się zupełnie samotny, jakby nikt mnie nie rozumiał",
        "Ciągle zawodzę i czuję się tak winny przed Bogiem",
        "Moje serce jest dziś pełne wdzięczności i chcę dziękować",
    ],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", choices=sorted(MOODS))
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    from fastapi.testclient import TestClient

    import app as appmod

    client = TestClient(appmod.app)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    langs = [args.lang] if args.lang else sorted(MOODS)

    def run_one(lang_mood):
        lang, mood = lang_mood
        r = client.post("/recommend", json={"mood": mood, "lang": lang})
        body = r.json()
        return lang, {"mood": mood, "results": body.get("results"), "error": body.get("error")}

    jobs = [(lang, mood) for lang in langs for mood in MOODS[lang]]
    by_lang: dict[str, list] = {lang: [] for lang in langs}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for lang, sample in pool.map(run_one, jobs):
            by_lang[lang].append(sample)
            print(f"[{lang}] {sample['mood'][:40]}… → {len(sample['results'] or [])}건")

    for lang, samples in by_lang.items():
        path = out_dir / f"{lang}.json"
        path.write_text(
            json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"저장: {path}")


if __name__ == "__main__":
    main()
