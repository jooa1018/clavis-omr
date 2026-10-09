"""Shared W5 strip extraction through W6 graph and validated lattice draft."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from clavis.contracts.common import Producer
from clavis.contracts.geometry import DewarpMesh, Staff
from clavis.contracts.symbols import SymbolGraph
from clavis.geometry import GeometryConfig, extract_strip, load_config
from clavis.symbols.detection import Settings, Template, detect
from clavis.symbols.reading import ReadingDraft, draft_reading


@dataclass(frozen=True)
class StaffReading:
    channels: NDArray[np.uint8]
    mesh: DewarpMesh
    graph: SymbolGraph
    reading: ReadingDraft


def read_staff(
    page: NDArray[np.uint8],
    staff: Staff,
    *,
    templates: list[Template],
    settings: Settings,
    producer: Producer,
    geometry_config: GeometryConfig | None = None,
) -> StaffReading:
    """Keep missing attributes unresolved, including on an empty valid lattice."""
    config = geometry_config or load_config()
    channels, mesh = extract_strip(page, staff, config=config)
    graph = detect(
        channels[:, :, 0],
        channels[:, :, 1],
        staff_id=staff.staff_id,
        staff_space=config["strip.s_star"],
        v_top=config["strip.above"] * config["strip.s_star"],
        templates=templates,
        settings=settings,
        producer=producer,
    )
    return StaffReading(channels, mesh, graph, draft_reading(graph, producer))
