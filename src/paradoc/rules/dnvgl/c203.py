import json
import pathlib

this_dir = pathlib.Path(__file__).parent

sn = json.load(open(this_dir.parent / "resources/sncurves.json"))["data"]


def alloweable_stress_range(nt, dff, thickf, scf, sn_curve):
    """

    :param nt: Number of cycles (N_{t}) [-]
    :param dff: Damage Fatigue Factor (DFF) [-]
    :param thickf: Thickness Effect (T_{f}) [-]
    :param scf: Stress Concentration Factor (SCF) [-]
    :param sn_curve: SN-Curve
    :return: Allowable Stress Range
    """
    a = 10 ** sn[sn_curve][1]
    m = sn[sn_curve][0]
    return (1 / (scf * thickf)) * ((a * 0.99 / (nt * dff)) ** (1 / m))
