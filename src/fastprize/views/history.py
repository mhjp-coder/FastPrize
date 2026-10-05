from fasthtml.common import (
    H1,
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

from fastprize.ui import document


def register_routes(rt, store):
    @rt("/events/{event_id}/history")
    def history_page(event_id: int):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        history = store.draw_history(event_id)
        rows = [
            Tr(
                Td(Strong(draw["entrant_name"]), Small(draw["organization"])),
                Td(Strong(draw["prize_name"]), Small(draw["sponsor"])),
                Td(draw["created_at"].replace("T", " ")[:16]),
            )
            for draw in history
        ]
        return document(
            f"FastPrize | {event['name']} | Draw history",
            Div(
                Div("COMPLETED DRAWS", cls="upper small-text secondary-text"),
                H1("Draw history", cls="small"),
                P(f"{len(history)} completed"),
                cls="vertical",
            ),
            Div(
                Table(
                    Thead(Tr(Th("Winner"), Th("Prize"), Th("Time"))),
                    Tbody(*rows),
                    cls="border stripes",
                ),
                cls="responsive scroll",
            )
            if history
            else P("Completed draws will appear here.", cls="surface-variant padding"),
            event_id=event_id,
            event_name=event["name"],
            active_link="history",
        )
