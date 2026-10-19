from fasthtml.common import (
    Div,
    HTTPException,
    P,
    Small,
    Strong,
    Table,
    Tbody,
    Td,
    Th,
    Thead,
    Tr,
)

from fastprize.ui import document, page_header


def register_routes(rt, store):
    @rt("/events/{event_id}/history")
    def history_page(event_id: int):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        history = store.draw_history(event_id)
        rows = [
            Tr(
                Td(
                    Div(
                        Strong(draw["entrant_name"]),
                        Small(draw["organization"]) if draw["organization"] else "",
                        cls="record-main",
                    )
                ),
                Td(
                    Div(
                        Strong(draw["prize_name"]),
                        Small(draw["sponsor"]) if draw["sponsor"] else "",
                        cls="record-main",
                    )
                ),
                Td(draw["created_at"].replace("T", " ")[:16]),
            )
            for draw in history
        ]
        history_table = (
            Table(
                Thead(Tr(Th("Winner"), Th("Prize"), Th("Time"))),
                Tbody(*rows),
                cls="uk-table uk-table-divider",
            )
            if history
            else P("Completed draws will appear here.", cls="empty-note")
        )
        return document(
            f"FastPrize | {event['name']} | Draw history",
            page_header(
                "Completed draws",
                "Draw history",
                f"{len(history)} completed",
            ),
            history_table,
            event_id=event_id,
            event_name=event["name"],
            active_link="history",
        )
