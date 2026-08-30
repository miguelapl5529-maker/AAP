from aap.core.evaluation.store import list_evaluations, record_evaluation


def test_record_and_list_evaluations_roundtrip():
    record_evaluation("v1", kind="rubric", metrics={"passed": 2, "total": 2}, eval_set="evals/x.jsonl", score=1.0)
    record_evaluation("v1", kind="rubric", metrics={"passed": 1, "total": 2}, eval_set="evals/x.jsonl", score=0.5)
    record_evaluation("v2", kind="rubric", metrics={"passed": 2, "total": 2}, score=1.0)

    evals_v1 = list_evaluations("v1")
    assert len(evals_v1) == 2
    assert evals_v1[0]["score"] == 0.5  # más reciente primero
    assert evals_v1[0]["metrics"] == {"passed": 1, "total": 2}

    assert len(list_evaluations("v2")) == 1


def test_evaluations_never_overwrite_previous_ones():
    for i in range(3):
        record_evaluation("v1", kind="rubric", metrics={"run": i}, score=i / 3)
    assert len(list_evaluations("v1")) == 3
