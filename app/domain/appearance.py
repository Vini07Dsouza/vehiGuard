"""Compare two vehicle appearances (FR-APP-03/04/05, task 5.4).

An attribute is only compared when BOTH values are known. UNKNOWN (poor
light, small or blurred crop) never causes a mismatch. OTHER is also not
compared: it is the catch-all for unusual hues and for colours that bad
light pushes out of the main families, so treating it as a different colour
would raise false alarms (ADR-09, ADR-11).

RM compares a sighting with the registry record; AM compares it with the
plate's earlier sighting. Both use compare().
"""

from dataclasses import dataclass

from app.domain.states import ColourFamily, VehicleType

NOT_COMPARABLE_COLOURS = frozenset({ColourFamily.UNKNOWN, ColourFamily.OTHER})


@dataclass(frozen=True)
class Appearance:
    vehicle_type: VehicleType
    colour_family: ColourFamily


@dataclass(frozen=True)
class AppearanceDiff:
    type_mismatch: bool
    colour_mismatch: bool

    @property
    def mismatch(self) -> bool:
        return self.type_mismatch or self.colour_mismatch

    def describe(self, a: Appearance, b: Appearance) -> list[str]:
        parts = []
        if self.type_mismatch:
            parts.append(f"type {a.vehicle_type} vs {b.vehicle_type}")
        if self.colour_mismatch:
            parts.append(f"colour {a.colour_family} vs {b.colour_family}")
        return parts


def compare(a: Appearance, b: Appearance) -> AppearanceDiff:
    type_known = VehicleType.UNKNOWN not in (a.vehicle_type, b.vehicle_type)
    colour_known = not ({a.colour_family, b.colour_family} & NOT_COMPARABLE_COLOURS)
    return AppearanceDiff(
        type_mismatch=type_known and a.vehicle_type != b.vehicle_type,
        colour_mismatch=colour_known and a.colour_family != b.colour_family,
    )
