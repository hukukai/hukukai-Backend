import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from chat.rag import debug_retrieve_mevzuat

TEST_CASES_PATH = ROOT_DIR / "tests" / "retrieval_test_cases_pending.json"

def load_test_cases():
    with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def doc_key(doc: dict) -> tuple[str, str, str]:
    return (
        str(doc.get("kanun_no") or ""),
        str(doc.get("madde_tipi") or "madde"),
        str(doc.get("madde_no") or ""),
    )


def expected_doc_key(doc: dict) -> tuple[str, str, str]:
    return (
        str(doc.get("kanun_no") or ""),
        str(doc.get("madde_tipi") or "madde"),
        str(doc.get("madde_no") or ""),
    )


def main():
    cases = load_test_cases()

    total = 0

    passed_resolved = 0
    total_resolved = 0

    passed_intent = 0
    total_intent = 0

    passed_top1 = 0
    total_top1 = 0

    passed_topdocs = 0
    total_topdocs = 0

    print("=" * 80)
    print("RETRIEVAL BENCHMARK")
    print("=" * 80)

    for case in cases:
        case_id = case.get("id", "unknown_case")
        question = case["question"]
        history = case.get("history", [])
        expected = case.get("expected", {})

        result = debug_retrieve_mevzuat(question, history=history)
        total += 1

        resolved_ok = True
        intent_ok = True
        top1_ok = True
        topdocs_ok = True

        if "resolved_question" in expected:
            total_resolved += 1
            resolved_ok = result.get("resolved_question") == expected["resolved_question"]
            if resolved_ok:
                passed_resolved += 1

        if "karar_retrieval_intent" in expected:
            total_intent += 1
            intent_ok = result.get("karar_retrieval_intent") == expected["karar_retrieval_intent"]
            if intent_ok:
                passed_intent += 1

        actual_docs = result.get("docs", [])
        actual_keys = [doc_key(d) for d in actual_docs]

        if "top_docs" in expected:
            expected_keys = [expected_doc_key(d) for d in expected["top_docs"]]

            # top-1 accuracy
            if expected_keys:
                total_top1 += 1
                top1_ok = len(actual_keys) > 0 and actual_keys[0] == expected_keys[0]
                if top1_ok:
                    passed_top1 += 1

            # all expected docs present
            total_topdocs += 1
            missing = [k for k in expected_keys if k not in actual_keys]
            topdocs_ok = len(missing) == 0
            if topdocs_ok:
                passed_topdocs += 1

        print(f"\n[{case_id}]")
        print(f"Question: {question}")
        print(f"Resolved: {result.get('resolved_question')}")
        print(f"Intent:   {result.get('karar_retrieval_intent')}")
        print(f"Count:    {result.get('count')}")

        if actual_docs:
            print("Top docs:")
            for d in actual_docs[:5]:
                print(
                    f"  - ({d.get('kanun_no')}, {d.get('madde_tipi')}, {d.get('madde_no')}) "
                    f"[{d.get('retrieval_source')}] score={d.get('rank_score')}"
                )

        print(
            f"Checks -> resolved:{resolved_ok} intent:{intent_ok} "
            f"top1:{top1_ok} topdocs:{topdocs_ok}"
        )

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total cases: {total}")
    print(f"Resolved accuracy: {passed_resolved}/{total_resolved}")
    print(f"Intent accuracy:   {passed_intent}/{total_intent}")
    print(f"Top-1 accuracy:    {passed_top1}/{total_top1}")
    print(f"Top-docs coverage: {passed_topdocs}/{total_topdocs}")
    print("=" * 80)


if __name__ == "__main__":
    main()