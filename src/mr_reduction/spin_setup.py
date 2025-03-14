from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Optional

from orsopy.fileio.data_source import Polarization as ORSOPolarization

from mr_reduction.simple_utils import SampleLogs
from mr_reduction.types import MantidWorkspace


class SpinState(IntEnum):
    """Enum for the spin state of the sample."""

    DOWN = -1
    UNPOLARIZED = 0
    UP = 1

    @property
    def as_orso(self) -> str:
        """Return the ORSO string representation of the spin state."""
        spin_state_dict = {-1: "m", 0: "o", 1: "p"}
        return spin_state_dict.get(self, ValueError(f"Invalid spin state: {self}"))


class REFMSpinSelectorState(Enum):
    """Available states for either the polarizer or analyzer. "OFF" doesn't mean a non-working selector

    Sample log "cross_section_id" is of type str, and its value defines the state of the polarizer-analyzer
    setup, such as "On_Off", "Off_Off", "On_On", etc. This is true if the polarizer and analyzer are installed
    and their types known. If the polarizer or analyzer is not installed or its type is not known, then its
    state ("Off") as given by log "cross_section_id" is meaningless.
    """

    OFF = "Off"
    ON = "On"


class REFMPolarizerVariant(IntEnum):
    """Available polarizers in REF_F

    Sample log "Polarizer" is of type int, and its value defines the polarizer variant.
    """

    NONE = 0  # no polarizer
    REFLECTION = 1  # reflection polarizer
    TRANSMISSION = 2  # transmission polarizer
    UNDEFINED = 3  # a polarizer may be installed but we don't know its type


@dataclass
class REFMPolarizer:
    variant: REFMPolarizerVariant
    state: Optional[REFMSpinSelectorState] = (
        None  # None makes sense only if polarizer not installed or type is unknown
    )

    @property
    def spin(self) -> SpinState:
        """Return the spin state of the polarizer."""
        if self.variant in (REFMPolarizerVariant.NONE, REFMPolarizerVariant.UNDEFINED):
            return SpinState.UNPOLARIZED
        elif self.variant == REFMPolarizerVariant.REFLECTION:
            return SpinState.DOWN if self.state == REFMSpinSelectorState.ON else SpinState.UP
        elif self.variant == REFMPolarizerVariant.TRANSMISSION:
            return SpinState.UP if self.state == REFMSpinSelectorState.ON else SpinState.DOWN
        else:
            raise ValueError(f"Invalid polarizer variant: {self.variant}")

    @property
    def installed_and_known(self) -> bool:
        """Return True if the polarizer is installed and we now which polarizer variant it is."""
        return self.variant not in (REFMPolarizerVariant.NONE, REFMPolarizerVariant.UNDEFINED)


class REFMAnalyzerVariant(IntEnum):
    """Available analyzers in REF_F

    Sample log "Analyzer" is of type int, and its value defines the analyzer variant.
    """

    NONE = 0  # no analyzer
    FAN = 1  # Fan analyzer
    THREE_He = 2  # 3He analyzer
    UNDEFINED = 3  # an analyzer may be installed but we don't know its type


@dataclass
class REFMAnalyzer:
    variant: REFMAnalyzerVariant
    state: Optional[REFMSpinSelectorState] = None  # None makes sense only if analyzer not installed or type is unknown

    @property
    def spin(self) -> SpinState:
        """Return the spin state of the analyzer."""
        if self.variant in (REFMAnalyzerVariant.NONE, REFMAnalyzerVariant.UNDEFINED):
            return SpinState.UNPOLARIZED
        elif self.variant == REFMAnalyzerVariant.FAN:
            return SpinState.DOWN if self.state == REFMSpinSelectorState.ON else SpinState.UP
        elif self.variant == REFMAnalyzerVariant.THREE_He:
            return SpinState.UP if self.state == REFMSpinSelectorState.ON else SpinState.DOWN
        else:
            raise ValueError(f"Invalid analyzer variant: {self.variant}")

    @property
    def installed_and_known(self) -> bool:
        """Return True if the analyzer is installed and we now which analyzer variant it is.."""
        return self.variant not in (REFMAnalyzerVariant.NONE, REFMAnalyzerVariant.UNDEFINED)


@dataclass
class REFMSpinSetup:
    """Specify both the polarizer and analyzer in a REF_M experiment"""

    polarizer: REFMPolarizer
    analyzer: REFMAnalyzer

    @classmethod
    def from_workspace(cls, workspace: MantidWorkspace) -> "REFMSpinSetup":
        """Create a REFMSpinSetup instance from a workspace with a unique polarizer-analyzer cross-section.

        Parameters
        ----------
        workspace: MantidWorkspace
            Workspace containing log "cross_section_id" with polarizer-analyzer state such as "On_Off" or "Off_Off".
        """
        logs = SampleLogs(workspace)

        polarizer = REFMPolarizer(variant=REFMPolarizerVariant(int(logs["Polarizer"])))
        analyzer = REFMAnalyzer(variant=REFMAnalyzerVariant(int(logs["Analyzer"])))

        if polarizer.installed_and_known is False and analyzer.installed_and_known is False:
            return cls(polarizer=polarizer, analyzer=analyzer)  # a spin setup with no polarizer or analyzer

        # find the state of the polarizer and analyzer from log entry cross_section_id
        cross_section_label = logs["cross_section_id"]  # e.g. "Off_Off", "On_Off"
        p_state, a_state = [REFMSpinSelectorState(x) for x in cross_section_label.split("_")]
        if polarizer.installed_and_known:  # polarizer is installed and we know its type
            polarizer.state = p_state
        if analyzer.installed_and_known:  # analyzer is installed and we know its type
            analyzer.state = a_state
        return cls(polarizer=polarizer, analyzer=analyzer)

    @property
    def as_orso(self) -> ORSOPolarization:
        """Polarization of the spin setup as an orsopy.fileio.data_source.Polarization instance"""
        pair = f"{self.polarizer.spin.as_orso}{self.analyzer.spin.as_orso}"
        if pair == "oo":
            pair = "unpolarized"
        return ORSOPolarization(pair)
