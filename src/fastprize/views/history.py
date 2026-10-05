from fasthtml.common import H1, Div, P, Section, Small, Strong
from starlette.exceptions import HTTPException

from fastprize.ui import document


def register_routes(rt, store):
    @rt("/events/{event_id}/history")
    def history_page(event_id: int):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        history = store.draw_history(event_id)
        rows = [
            Div(
                Div(
                    Strong(draw["entrant_name"]),
                    Small(draw["organization"]),
                    class_="history-cell",
                ),
                Div(
                    Strong(draw["prize_name"]),
                    Small(draw["sponsor"]),
                    class_="history-cell",
                ),
                Div(
                    draw["created_at"].replace("T", " ")[:16],
                    class_="history-cell",
                ),
                class_="history-row",
            )
            for draw in history
        ]
        return document(
            f"FastPrize | {event['name']} | Draw history",
            Div(
                Div("COMPLETED DRAWS", class_="eyebrow"),
                H1("Draw history"),
                P(f"{len(history)} completed"),
                class_="page-intro",
            ),
            Section(
                Div(
                    Div("Winner", class_="history-head"),
                    Div("Prize", class_="history-head"),
                    Div("Time", class_="history-head"),
                    class_="history-row history-title",
                ),
                *rows,
                class_="history",
            )
            if history
            else P("Completed draws will appear here.", class_="empty"),
            event_id=event_id,
            event_name=event["name"],
            active_link="history",
        )
