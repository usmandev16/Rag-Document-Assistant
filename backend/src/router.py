"""LangGraph router: send spreadsheet counting/total questions to pandas.

    classify --documents--> END   (caller runs the normal RAG pipeline, unchanged)
       |
       +--spreadsheet--> plan --> execute --ok--> answer --> END
                                     |
                                     +--invalid plan--> END ("I don't know.")

The LLM classifies with only the question plus sheet names and columns, then
returns a JSON query plan. sheets.validate_plan / execute_plan run it with
fixed pandas code; LLM output is never executed.
"""
import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from src import sheets
from src.llm import STYLE_RULE, _create

DONT_KNOW = "I don't know."


class RouteState(TypedDict, total=False):
    question: str
    chat_id: str
    sheets: list[dict]
    route: str            # "documents" | "spreadsheet"
    plan: dict
    entry: dict           # the validated sheet
    result: dict          # computed by pandas
    error: str            # why the plan was rejected
    answer: str
    tokens: int


ROUTE_SCHEMA = {
    "type": "object",
    "properties": {"route": {"type": "string", "enum": ["documents", "spreadsheet"]}},
    "required": ["route"],
    "additionalProperties": False,
}

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "answerable": {"type": "boolean"},
        "sheet": {"type": "string"},
        "filters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "op": {"type": "string", "enum": sorted(sheets.OPS)},
                    "value": {"type": "string"},
                },
                "required": ["column", "op", "value"],
                "additionalProperties": False,
            },
        },
        "group_by": {"type": ["string", "null"]},
        "aggregate": {
            "type": "object",
            "properties": {
                "column": {"type": ["string", "null"]},
                "func": {"type": "string", "enum": sorted(sheets.FUNCS)},
            },
            "required": ["column", "func"],
            "additionalProperties": False,
        },
    },
    "required": ["answerable", "sheet", "filters", "group_by", "aggregate"],
    "additionalProperties": False,
}


async def _json_call(kind: str, prompt: str, name: str, schema: dict) -> tuple[dict, int]:
    response = await _create(
        kind,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        reasoning_effort="low",
        response_format={"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}},
    )
    return json.loads(response.choices[0].message.content), response.usage.total_tokens


async def classify(state: RouteState) -> RouteState:
    # Only the question and sheet names/columns: no rows, no document text.
    listing = "\n".join(f"- {s['name']}: {', '.join(s['columns'])}" for s in state["sheets"])
    prompt = (
        "Decide how to answer the user's question.\n"
        '"spreadsheet": it needs counting, totals, averages, maximum/minimum, or filtering '
        "rows across one of the spreadsheets below.\n"
        '"documents": anything else, including looking up a single fact, or questions the '
        "spreadsheet columns can't answer.\n\n"
        f"Spreadsheets:\n{listing}\n\nQuestion: {state['question']}"
    )
    out, tokens = await _json_call("route", prompt, "route", ROUTE_SCHEMA)
    return {"route": out["route"], "tokens": state.get("tokens", 0) + tokens}


async def plan(state: RouteState) -> RouteState:
    described = "\n\n".join(sheets.describe_sheet(state["chat_id"], s) for s in state["sheets"])
    prompt = (
        "Write a query plan that answers the question from one spreadsheet.\n"
        "- sheet: the exact sheet name.\n"
        "- filters: rows to keep, all must match. op is one of ==, !=, >, <, contains. "
        "== and contains ignore case. > and < need a number. Use the value formats shown "
        "in the examples (e.g. dates exactly as written in the sheet).\n"
        "- group_by: a column to group by, or null.\n"
        "- aggregate: func is one of count, sum, mean, max, min; column is the column to "
        "aggregate, or null for count of rows.\n"
        "- answerable: false if these columns can't answer the question exactly "
        "(e.g. it needs a column that doesn't exist, or a calculation other than "
        "count/sum/mean/max/min).\n\n"
        f"{described}\n\nQuestion: {state['question']}"
    )
    out, tokens = await _json_call("plan", prompt, "query_plan", PLAN_SCHEMA)
    return {"plan": out, "tokens": state.get("tokens", 0) + tokens}


async def execute(state: RouteState) -> RouteState:
    plan_ = state["plan"]
    if not plan_.get("answerable"):
        return {"error": "plan marked not answerable", "answer": DONT_KNOW}
    try:
        entry = sheets.validate_plan(plan_, state["sheets"])
        result = sheets.execute_plan(state["chat_id"], entry, plan_)
    except sheets.PlanError as exc:
        return {"error": str(exc), "answer": DONT_KNOW}
    return {"entry": entry, "result": result}


async def answer(state: RouteState) -> RouteState:
    result = state["result"]
    prompt = (
        "Answer the user's question using only this result, which was computed with "
        "pandas over every row of the spreadsheet. Give the number(s) plainly and cite "
        f"the file as [1] ({result['source']}). If the result does not answer the "
        'question exactly, reply exactly "I don\'t know." ' + STYLE_RULE + "\n\n"
        f"Question: {state['question']}\n"
        f"Query plan: {json.dumps(state['plan'], ensure_ascii=False)}\n"
        f"Result: {json.dumps(result, ensure_ascii=False)}"
    )
    response = await _create("sheet_answer", messages=[{"role": "user", "content": prompt}], temperature=0)
    return {"answer": response.choices[0].message.content or DONT_KNOW,
            "tokens": state.get("tokens", 0) + response.usage.total_tokens}


def _build():
    graph = StateGraph(RouteState)
    graph.add_node("classify", classify)
    graph.add_node("plan", plan)
    graph.add_node("execute", execute)
    graph.add_node("answer", answer)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", lambda s: s["route"], {"documents": END, "spreadsheet": "plan"})
    graph.add_edge("plan", "execute")
    graph.add_conditional_edges("execute", lambda s: "fail" if s.get("error") else "ok", {"fail": END, "ok": "answer"})
    graph.add_edge("answer", END)
    return graph.compile()


GRAPH = _build()


async def route_question(question: str, chat_id: str) -> RouteState:
    """Run the router. route == "documents" means: use the normal RAG
    pipeline. Chats without spreadsheets skip the LLM call entirely."""
    available = sheets.list_sheets(chat_id)
    if not available:
        return {"route": "documents", "tokens": 0}
    return await GRAPH.ainvoke({"question": question, "chat_id": chat_id, "sheets": available, "tokens": 0})


def sources_for(state: RouteState) -> list[tuple[str, dict]]:
    """The computed result as a single citable 'passage' for keep_cited."""
    result = state.get("result")
    if not result:
        return []
    summary = f"Computed with pandas over {result['sheet']}: {result['aggregate']} " \
              f"on {result['rows_matching_filters']} of {result['rows_in_sheet']} rows"
    return [(summary, {"source": result["source"], "chunk_index": None})]
