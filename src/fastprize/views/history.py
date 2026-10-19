from fasthtml.common import (
    H1,
    Article,
    Br,
    Div,
    HTTPException,
    P,
    Small,
    Span,
    Strong,
    Table,
    Tbody,
    Td,
    Th,
    Thead,
    Time,
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
                Td(
                    Div(
                        Strong(draw["entrant_name"]),
                        Small(draw["organization"]),
                        cls="vertical",
                    )
                ),
                Td(
                    Div(
                        Strong(draw["prize_name"]),
                        Small(draw["sponsor"]),
                        cls="vertical",
                    )
                ),
                Td(
                    Time(
                        Span(draw["created_at"][:10], data_history_date="true"),
                        Br(cls="s"),
                        Span(" ", cls="m l"),
                        Span(
                            f"{draw['created_at'][11:16]} UTC",
                            data_history_clock="true",
                        ),
                        datetime=draw["created_at"],
                        data_history_time="true",
                    )
                ),
            )
            for draw in history
        ]
        history_content = (
            Article(
                Div(
                    Table(
                        Thead(
                            Tr(
                                Th("Winner"),
                                Th("Prize"),
                                Th("Time"),
                            )
                        ),
                        Tbody(*rows),
                        cls="stripes",
                    ),
                    cls="responsive scroll",
                ),
                cls="card padding secondary-container small-round vertical bottom-padding",
            )
            if history
            else Article(
                P("Completed draws will appear here."),
                cls="card padding secondary-container small-round vertical",
            )
        )
        return document(
            f"FastPrize | {event['name']} | Draw history",
            Article(
                H1("Draw history", cls="small"),
                P(f"{len(history)} completed"),
                cls="card padding primary-container small-round vertical bottom-margin",
            ),
            history_content,
            event_id=event_id,
            active_link="history",
        )
