import httpx

from backend.config import HA_TOKEN, HA_URL, SOURCES
from backend.fetchers import FetchResult

SOURCE = "home_assistant"


def _format_state(state: str, unit: str) -> str:
    """EUR/kWh -> snt/kWh, koska sähkön hinta on tutumpi senteissä."""
    if unit == "EUR/kWh":
        try:
            return f"{float(state) * 100:.2f} snt/kWh"
        except ValueError:
            pass
    return f"{state} {unit}".strip()


async def fetch() -> list[FetchResult]:
    cfg = SOURCES.get("home_assistant", {})
    if not cfg.get("enabled", True):
        return []

    headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}
    results = []

    async with httpx.AsyncClient(timeout=10) as client:
        # Entiteettien tilat. Listan alkio voi olla joko pelkkä entiteetti-ID
        # (string, lukee state-kentän) tai dict jos halutaan lukea attribuutti:
        #   - entity: climate.huonetermostaatti
        #     attribute: current_temperature
        #     name: "Huonelämpötila"   # valinnainen, korvaa friendly_namen
        #     unit: "°C"               # valinnainen, attribuuteilla ei ole omaa yksikköä
        for entity_cfg in cfg.get("entities", []):
            if isinstance(entity_cfg, str):
                entity_id, attribute, name_override, unit_override = entity_cfg, None, None, None
            else:
                entity_id = entity_cfg["entity"]
                attribute = entity_cfg.get("attribute")
                name_override = entity_cfg.get("name")
                unit_override = entity_cfg.get("unit")

            resp = await client.get(f"{HA_URL}/api/states/{entity_id}", headers=headers)
            if resp.status_code != 200:
                continue

            data = resp.json()
            attrs = data.get("attributes", {})
            friendly = name_override or attrs.get("friendly_name", entity_id)

            if attribute:
                value = attrs.get(attribute, "?")
                detail = f"{value} {unit_override or ''}".strip()
            else:
                state = data.get("state", "?")
                unit = unit_override or attrs.get("unit_of_measurement", "")
                detail = _format_state(state, unit)

            results.append(FetchResult(source=SOURCE, title=friendly, detail=detail))

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
