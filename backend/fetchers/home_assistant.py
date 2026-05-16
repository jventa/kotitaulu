import httpx

from backend.config import HA_TOKEN, HA_URL, SOURCES
from backend.fetchers import FetchResult

SOURCE = "home_assistant"


async def fetch() -> list[FetchResult]:
    cfg = SOURCES.get("home_assistant", {})
    if not cfg.get("enabled", True):
        return []

    headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}
    results = []

    async with httpx.AsyncClient(timeout=10) as client:
        # Entiteettien tilat
        for entity_id in cfg.get("entities", []):
            resp = await client.get(f"{HA_URL}/api/states/{entity_id}", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                state = data.get("state", "?")
                attrs = data.get("attributes", {})
                friendly = attrs.get("friendly_name", entity_id)
                unit = attrs.get("unit_of_measurement", "")
                results.append(
                    FetchResult(
                        source=SOURCE,
                        title=friendly,
                        detail=f"{state} {unit}".strip(),
                    )
                )

        # Todo-listat
        for list_entity in cfg.get("todo_lists", []):
            resp = await client.post(
                f"{HA_URL}/api/services/todo/get_items",
                headers=headers,
                json={"entity_id": list_entity},
            )
            if resp.status_code in (200, 201):
                items = resp.json()
                all_items = items.get("response", {}).get(list_entity, {}).get("items", [])
                for item in [i for i in all_items if i.get("status", "needs_action") == "needs_action"]:
                    results.append(
                        FetchResult(
                            source=SOURCE,
                            title=item.get("summary", ""),
                            detail=list_entity.replace("todo.", "").replace("_", " ").title(),
                            priority="normal",
                        )
                    )

    return results
