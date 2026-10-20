from fasthtml.common import A, Div, HTTPException, P, Strong, Time
from monsterui.franken import (
    Card,
    Grid,
    Placeholder,
    Small,
    Table,
    TableT,
    Tbody,
    Td,
    TextT,
    Th,
    Thead,
    Tr,
)

from fastprize.ui import (
    PAGE_SIZE,
    document,
    list_pagination,
    page_header,
    record_body,
    search_field,
    stat_card,
)


def register_routes(rt, store):
    @rt("/events/{event_id}/history")
    def history_page(event_id: int):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        history = store.draw_history(event_id)
        rows = []
        for index, draw in enumerate(history):
            prize_href = (
                f"/events/{event_id}/prizes#prize-{draw['prize_id']}"
                if draw.get("prize_id")
                else None
            )
            winner = Strong(draw["entrant_name"])
            if prize_href:
                winner = A(winner, href=prize_href, cls="history-link")
            rows.append(
                Tr(
                    Td(
                        record_body(
                            winner,
                            Small(draw["organization"], cls=TextT.meta)
                            if draw["organization"]
                            else "",
                        ),
                        data_label="Winner",
                    ),
                    Td(
                        record_body(
                            Strong(draw["prize_name"]),
                            Small(draw["sponsor"], cls=TextT.meta)
                            if draw["sponsor"]
                            else "",
                        ),
                        data_label="Prize",
                    ),
                    Td(
                        Time(
                            draw["created_at"].replace("T", " ")[:16],
                            datetime=draw["created_at"],
                            cls="history-time",
                        ),
                        data_label="Time",
                    ),
                    cls="history-draw" if prize_href else None,
                    data_href=prize_href,
                    tabindex="0" if prize_href else None,
                    role="link" if prize_href else None,
                    aria_label=(
                        f"Show {draw['prize_name']} on the prize list"
                        if prize_href
                        else None
                    ),
                    onclick=(
                        "if (event.target.closest('a')) return; "
                        "window.location = this.dataset.href"
                        if prize_href
                        else None
                    ),
                    onkeydown=(
                        "if (event.key === 'Enter') window.location = this.dataset.href"
                        if prize_href
                        else None
                    ),
                    data_search=" ".join(
                        part
                        for part in (
                            draw["entrant_name"],
                            draw["organization"],
                            draw["prize_name"],
                            draw["sponsor"],
                            draw["created_at"].replace("T", " ")[:16],
                        )
                        if part
                    ).lower(),
                    data_page_match="1",
                    hidden=True if index >= PAGE_SIZE else None,
                )
            )
        history_table = (
            Table(
                Thead(Tr(Th("Winner"), Th("Prize"), Th("Time"))),
                Tbody(*rows, id="history-list"),
                cls=(TableT.middle, TableT.divider, TableT.hover, TableT.sm, "history-table"),
            )
            if history
            else Placeholder(P("Completed draws will appear here."))
        )
        return document(
            f"FastPrize | {event['name']} | Draw history",
            page_header("Draw history"),
            Grid(
                stat_card(len(history), "draws completed"),
                cols_sm=1,
                cols_md=2,
                cols_lg=2,
                cols_xl=2,
                cls="gap-6",
            ),
            Card(
                Div(
                    search_field("history-list", "Search draws"),
                    cls="list-search",
                ),
                history_table,
                list_pagination("history-list", len(history)) if history else "",
                cls="history-card",
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="history",
        )
