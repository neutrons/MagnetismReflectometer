from unittest.mock import Mock, patch

import pytest
from mr_reduction.spin_setup import (
    REFMAnalyzerVariant,
    REFMPolarizerVariant,
    REFMSpinSelectorState,
    REFMSpinSetup,
    SpinState,
)


class TestREFMSpinSetup:
    def test_from_workspace(self):
        with patch("mr_reduction.spin_setup.SampleLogs", autospec=True) as SampleLogsMock:
            workspace = None
            SampleLogsMock.return_value = {
                "Polarizer": 1,  # reflection polarizer
                "Analyzer": 2,  # 3He analyzer
                "cross_section_id": "On_Off",
            }
            spin_setup = REFMSpinSetup.from_workspace(workspace)
            assert spin_setup.polarizer.variant == REFMPolarizerVariant.REFLECTION
            assert spin_setup.polarizer.state == REFMSpinSelectorState.ON
            assert spin_setup.analyzer.variant == REFMAnalyzerVariant.THREE_He
            assert spin_setup.analyzer.state == REFMSpinSelectorState.OFF
            assert spin_setup.as_orso.value == "mm"

            SampleLogsMock.return_value = {
                "Polarizer": 0,  # no polarizer
                "Analyzer": 0,  # no analyzer
            }
            spin_setup = REFMSpinSetup.from_workspace(workspace)
            assert spin_setup.polarizer.variant == REFMPolarizerVariant.NONE
            assert spin_setup.polarizer.state is None
            assert spin_setup.analyzer.variant == REFMAnalyzerVariant.NONE
            assert spin_setup.analyzer.state is None
            assert spin_setup.as_orso.value == "unpolarized"

            SampleLogsMock.return_value = {
                "Polarizer": 3,  # undefined polarizer
                "Analyzer": 3,  # undefined analyzer
            }
            spin_setup = REFMSpinSetup.from_workspace(workspace)
            assert spin_setup.polarizer.variant == REFMPolarizerVariant.UNDEFINED
            assert spin_setup.polarizer.state is None
            assert spin_setup.analyzer.variant == REFMAnalyzerVariant.UNDEFINED
            assert spin_setup.analyzer.state is None
            assert spin_setup.as_orso.value == "unpolarized"

            SampleLogsMock.return_value = {
                "Polarizer": 1,  # reflection polarizer
                "Analyzer": 3,  # undefined analyzer
                "cross_section_id": "On_Off",
            }
            spin_setup = REFMSpinSetup.from_workspace(workspace)
            assert spin_setup.polarizer.variant == REFMPolarizerVariant.REFLECTION
            assert spin_setup.polarizer.state == REFMSpinSelectorState.ON
            assert spin_setup.analyzer.variant == REFMAnalyzerVariant.UNDEFINED
            assert spin_setup.analyzer.state is None
            assert spin_setup.as_orso.value == "mo"

            SampleLogsMock.return_value = {
                "Polarizer": 0,  # reflection polarizer
                "Analyzer": 1,  # no analyzer installed
                "cross_section_id": "Off_On",
            }
            spin_setup = REFMSpinSetup.from_workspace(workspace)
            assert spin_setup.polarizer.variant == REFMPolarizerVariant.NONE
            assert spin_setup.polarizer.state is None
            assert spin_setup.analyzer.variant == REFMAnalyzerVariant.FAN
            assert spin_setup.analyzer.state == REFMSpinSelectorState.ON
            assert spin_setup.as_orso.value == "om"


if __name__ == "__main__":
    pytest.main([__file__])
