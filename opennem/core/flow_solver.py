"""OpenNEM Network Flows v3

Creates an aggregate table with network flows (imports/exports), emissions
and market_value

This feature is enabled behind a feature flag in settings_schema.network_flows_v3

Unit tests are at tests/core/flow_solver.py

Documentation at: https://github.com/opennem/opennem/wiki/Network-Flows

"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import NewType

import numpy as np
import pandas as pd

from opennem.schema.network import NetworkNEM, NetworkSchema

# from result import Err, Ok, Result

logger = logging.getLogger("opennem.core.flow_solver")


class FlowSolverException(Exception):
    "Raised on issue with flow solver"
    pass


# ex. NSW1
Region = NewType("Region", str)

# ex. NSW1->QLD1
RegionFlow = NewType("RegionFlow", str)


# Region demand and emissions structures
@dataclass
class RegionDemandEmissions:
    """Emissions for each region

    Emissions are the sum of the emissions for that region plus the emissions
    of the imports minus the emissions of the exports
    """

    interval: datetime
    region_code: Region
    network: NetworkSchema = NetworkNEM
    energy_mwh: float | None = None
    emissions_t: float = 0.0
    generated_mw: float | None = None

    @property
    def energy(self) -> float:
        """Energy in MWh"""
        if self.energy_mwh:
            return self.energy_mwh

        if self.generated_mw:
            return self.generated_mw / self.network.intervals_per_hour

        raise Exception(f"Could not get energy for {self.network.code} {self.region_code} at {self.interval}")

    @property
    def emissions_intensity(self) -> float:
        """Emissions intensity for the region"""
        return self.emissions_t / self.energy


class NetworkRegionsDemandEmissions:
    """For a network contains a list of regions and the demand and emissions for each
    region.
    """

    def __init__(self, network: NetworkSchema, data: list[RegionDemandEmissions]):
        self.data = data
        self.network = network

    def __repr__(self) -> str:
        return f"<RegionNetEmissionsDemandForNetwork region_code={self.network.code} regions={len(self.data)}>"

    def get_region(self, interval: datetime, region: Region) -> RegionDemandEmissions:
        """Get region by code"""
        region_result = list(filter(lambda x: x.interval == interval and x.region_code == region, self.data))

        if not region_result:
            raise FlowSolverException(f"Region {region} not found in network {self.network.code}")

        return region_result.pop()

    def to_dict(self) -> list[dict]:
        """Return flow results as a dictionary"""
        region_demand_emissions = [
            {
                "region_code": i.region_code,
                "generated_mwh": i.energy_mwh,
                "emissions_t": i.emissions_t,
            }
            for i in self.data
        ]

        return region_demand_emissions

    def to_dataframe(self) -> pd.DataFrame:
        """Get flow solver results as a dataframe"""
        region_demand_emissions = self.to_dict()

        region_df = pd.DataFrame.from_records(region_demand_emissions)

        return region_df


# Interconnector flow generation and emissions structures
@dataclass
class InterconnectorNetEmissionsEnergy:
    """Power for each interconnector

    Power is the sum of the generation of the source region minus the exports
    """

    interval: datetime
    region_flow: RegionFlow
    generated_mw: float
    energy_mwh: float

    @property
    def interconnector_region_from(self) -> str:
        """Region code for the interconnector source"""
        return self.region_flow.split("->")[0]

    @property
    def interconnector_region_to(self) -> str:
        """Region code for the interconnector destination"""
        return self.region_flow.split("->")[1]


class NetworkInterconnectorEnergyEmissions:
    """For a network contains a list of interconnectors and the emissions and generation for each"""

    def __init__(self, network: NetworkSchema, data: list[InterconnectorNetEmissionsEnergy]):
        self.data = data
        self.network = network

    def get_interconnector(
        self, interval: datetime, region_flow: RegionFlow, default: int = 0
    ) -> InterconnectorNetEmissionsEnergy:
        """Get interconnector by region flow"""
        interconnector_result = list(filter(lambda x: x.interval == interval and x.region_flow == region_flow, self.data))

        if not interconnector_result:
            if default:
                return InterconnectorNetEmissionsEnergy(
                    interval=interval, region_flow=region_flow, energy_mwh=default, generated_mw=default
                )

            avaliable_options = ", ".join([x.region_flow for x in self.data])

            raise FlowSolverException(
                f"Interconnector {interval} {region_flow} not found in network {self.network.code}. Available options: {avaliable_options}"
            )

        if len(interconnector_result) > 1:
            raise FlowSolverException(f"Interconnector {interval} {region_flow} has multiple results")

        return interconnector_result.pop()

    def to_dict(self) -> list[dict]:
        """Return flow results as a dictionary"""
        solver_results = [
            {
                "interconnector_region_from": i.interconnector_region_from,
                "interconnector_region_to": i.interconnector_region_to,
                "generated_mwh": i.energy_mwh,
            }
            for i in self.data
        ]

        return solver_results

    def to_dataframe(self) -> pd.DataFrame:
        """Get flow solver results as a dataframe"""
        interconnector_data = self.to_dict()

        interconnector_df = pd.DataFrame.from_records(interconnector_data)

        return interconnector_df


# Flow solver return class
@dataclass
class FlowSolverResultRecord:
    """ """

    interval: datetime
    region_flow: RegionFlow
    emissions_t: float
    generated_mw: float | None = None
    energy_mwh: float | None = None

    @property
    def interconnector_region_from(self) -> str:
        """Region code for the interconnector source"""
        return self.region_flow.split("->")[0]

    @property
    def interconnector_region_to(self) -> str:
        """Region code for the interconnector destination"""
        return self.region_flow.split("->")[1]


class FlowSolverResult:
    """Class to store flow solver results"""

    def __init__(self, data: list[FlowSolverResultRecord], network: NetworkSchema | None = None):
        self.network = network
        self.data = data

    def __repr__(self) -> str:
        return f"<FlowSolver network={self.network.code if self.network else ''} results={len(self.data)}>"

    def get_flow(self, interval: datetime, region_flow: RegionFlow, default: int = 0) -> FlowSolverResultRecord:
        """Get flow by region flow"""
        flow_result = list(filter(lambda x: x.region_flow == region_flow, self.data))

        if not flow_result:
            if default:
                return FlowSolverResultRecord(
                    interval=interval, region_flow=region_flow, emissions_t=default, generated_mw=default, energy_mwh=default
                )

            avaliable_options = ", ".join([x.region_flow for x in self.data])

            raise FlowSolverException(f"Flow {interval} interval {region_flow} not found. Available options: {avaliable_options}")

        return flow_result.pop()

    def to_dict(self) -> list[dict]:
        """Return flow results as a dictionary"""
        solver_results = [
            {
                "trading_interval": i.interval.replace(tzinfo=None),
                "interconnector_region_from": i.interconnector_region_from,
                "interconnector_region_to": i.interconnector_region_to,
                "emissions": i.emissions_t,
            }
            for i in self.data
        ]

        return solver_results

    def to_dataframe(self) -> pd.DataFrame:
        """Get flow solver results as a dataframe"""
        solver_results = self.to_dict()

        flow_emissions_df = pd.DataFrame.from_records(solver_results)

        return flow_emissions_df


def solve_flow_emissions_for_interval(
    interval: datetime,
    interconnector_data: NetworkInterconnectorEnergyEmissions,
    region_data: NetworkRegionsDemandEmissions,
) -> FlowSolverResult:
    """_summary_

    Args:
        interconnector_data: for each network, contains a list of interconnectors and
            the emissions and generation for each
        region_data: for each region, the emissions and generation

    Returns:
        List of FlowSolverResults for each interconnector with their emissions

    Example arguments:

    interconnector_data = [
        InterconnectorNetEmissionsEnergy(region_flow=RegionFlow('NSW1->QLD1'), generated_mwh=10.0, emissions_t=1.0),
        ...
    ]

    region_data = [
        RegionDemandEmissions(region_code=Region('NSW1'), generated_mwh=1000.0, emissions_t=350.0),
        ...
    ]

    Example return:

    [{region_flow: "NSW1->QLD1", emissions: 154.34}, {region_flow: "VIC1->NSW1", emissions: 0.0}, ...]


    Emissions
    """

    # these are the results we will return
    results = []

    a = np.array(
        [
            # emissions balance equations
            [1, 0, 0, 0, 0, 0, 0, 0, -1, 0],
            [0, 1, 0, 0, 0, 0, -1, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0, 0, 0, -1],
            [0, 0, 0, 1, 0, -1, 1, 1, 0, 0],
            [0, 0, 0, 0, 1, 1, 0, -1, 1, 1],
            # emissions intensity equations for flow-through regions
            [
                0,
                0,
                0,
                -interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("NSW1->QLD1")).energy_mwh
                / region_data.get_region(interval=interval, region=Region("NSW1")).energy_mwh,
                0,
                0,
                1,
                0,
                0,
                0,
            ],
            [
                0,
                0,
                0,
                -interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("NSW1->VIC1")).energy_mwh
                / region_data.get_region(interval=interval, region=Region("NSW1")).energy_mwh,
                0,
                0,
                0,
                1,
                0,
                0,
            ],
            [
                0,
                0,
                0,
                -interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("VIC1->TAS1")).energy_mwh
                / region_data.get_region(interval=interval, region=Region("VIC1")).energy_mwh,
                0,
                0,
                0,
                0,
                0,
                1,
            ],
            [
                0,
                0,
                0,
                -interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("VIC1->SA1")).energy_mwh
                / region_data.get_region(interval=interval, region=Region("VIC1")).energy_mwh,
                0,
                0,
                0,
                0,
                1,
                0,
            ],
            [
                0,
                0,
                0,
                -interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("VIC1->NSW1")).energy_mwh
                / region_data.get_region(interval=interval, region=Region("VIC1")).energy_mwh,
                1,
                0,
                0,
                0,
                0,
                0,
            ],
        ]
    )

    # net emissions for each region (region emissions )
    region_emissions = np.array(
        [
            # net emissions for each region (region emissions, minus exported, plus imported)
            [region_data.get_region(interval=interval, region=Region("SA1")).emissions_t],
            [region_data.get_region(interval=interval, region=Region("QLD1")).emissions_t],
            [region_data.get_region(interval=interval, region=Region("TAS1")).emissions_t],
            [region_data.get_region(interval=interval, region=Region("NSW1")).emissions_t],
            [region_data.get_region(interval=interval, region=Region("VIC1")).emissions_t],
            [0],
            [0],
            [0],
            [0],
            [0],
        ]
    )

    # cast nan to 0
    region_emissions = np.nan_to_num(region_emissions)

    # obtain solution
    np.linalg.solve(a, region_emissions)

    results.append(
        FlowSolverResultRecord(
            interval=interval,
            region_flow=RegionFlow("VIC1->NSW1"),
            emissions_t=interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("VIC1->NSW1")).energy_mwh
            * region_data.get_region(interval=interval, region=Region("VIC1")).emissions_intensity,
        )
    )
    results.append(
        FlowSolverResultRecord(
            interval=interval,
            region_flow=RegionFlow("NSW1->VIC1"),
            emissions_t=interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("NSW1->VIC1")).energy_mwh
            * region_data.get_region(interval=interval, region=Region("NSW1")).emissions_intensity,
        )
    )
    results.append(
        FlowSolverResultRecord(
            interval=interval,
            region_flow=RegionFlow("VIC1->SA1"),
            emissions_t=interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("VIC1->SA1")).energy_mwh
            * region_data.get_region(interval=interval, region=Region("VIC1")).emissions_intensity,
        )
    )
    results.append(
        FlowSolverResultRecord(
            interval=interval,
            region_flow=RegionFlow("VIC1->TAS1"),
            emissions_t=interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("VIC1->TAS1")).energy_mwh
            * region_data.get_region(interval=interval, region=Region("VIC1")).emissions_intensity,
        )
    )

    # simple flows
    results.append(
        FlowSolverResultRecord(
            interval=interval,
            region_flow=RegionFlow("QLD1->NSW1"),
            emissions_t=interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("QLD1->NSW1")).energy_mwh
            * region_data.get_region(interval=interval, region=Region("QLD1")).emissions_intensity,
        )
    )
    results.append(
        FlowSolverResultRecord(
            interval=interval,
            region_flow=RegionFlow("TAS1->VIC1"),
            emissions_t=interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("TAS1->VIC1")).energy_mwh
            * region_data.get_region(interval=interval, region=Region("TAS1")).emissions_intensity,
        )
    )
    results.append(
        FlowSolverResultRecord(
            interval=interval,
            region_flow=RegionFlow("SA1->VIC1"),
            emissions_t=interconnector_data.get_interconnector(interval=interval, region_flow=RegionFlow("SA1->VIC1")).energy_mwh
            * region_data.get_region(interval=interval, region=Region("SA1")).emissions_intensity,
        )
    )

    response_model = FlowSolverResult(data=results)

    return response_model


def solve_flow_emissions_for_interval_range(
    interconnector_data: NetworkInterconnectorEnergyEmissions,
    region_data: NetworkRegionsDemandEmissions,
) -> FlowSolverResult:
    """
    Solve flow emissions for interval range
    """

    intervals = list({i.interval for i in interconnector_data.data})

    logger.debug(f"Called with {len(intervals)} intervals")


# debugger entry point
if __name__ == "__main__":
    pass
