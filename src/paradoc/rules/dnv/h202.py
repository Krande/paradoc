import logging

import numpy as np


class Transport:
    """
    Unrestricted criteria world wide for transportation accelerations and wind force based on Table-3.1 in DNV-OS-H202

    x = distance from vessel/barge mid ship
    y = distance from vessel/barge centreline
    d = distance used for calculating az in quartering sea, d = (0.5 * x ** 2 + y ** 2) ** 0.5
    z = height above waterline
    ax = longitudinal acceleration parallel with barge deck
    ay = transverse acceleration parallel with barge deck
    az = acceleration normal to the barge deck at centre of barge.
    wind = kN / m ** 2

    The accelerations include the component for self-weight

    g = 9.80665 m / s ** 2
    :param acc_waterline: acceleration at waterline, as fraction of gravity [g = 9.80665 m / s ** 2]
    :param acc_per_height: acceleration increase for each meter above waterline, as fraction of gravity [g / m]
    :param hs:
    """

    g = 9.80665

    @staticmethod
    def acc_comb(barge, cargo, hs):
        def get_acc(a_dir):
            return np.array([Transport.acc(a_dir, acc_type, barge.p, cargo.p) for acc_type in acc_waterline[a_dir]])

        acc_waterline, acc_per_meter = Transport.get_criteria(hs)
        return np.array([get_acc(acc_dir) for acc_dir in acc_waterline])

    @staticmethod
    def acc(acc_dir, acc_type, hs, cog_barge, cog_cargo=None):
        def get_offset_arm():
            if acc_type == "pitch":
                return d_cog.x
            elif acc_type == "roll":
                return d_cog.y
            else:
                return np.sqrt(0.5 * d_cog.x ** 2 + d_cog.y ** 2)

        try:
            from ada import Node
        except ModuleNotFoundError as e:
            logging.error(f"{e}. To use this, you need to have the adapy-package available.")
            return e

        d_cog = cog_barge if cog_cargo is None else Node(cog_cargo.p - cog_barge.p)
        offset_arm = d_cog.z if acc_dir != "az" else get_offset_arm()

        acc_waterline, acc_per_meter = Transport.get_criteria(hs)
        acc = acc_waterline[acc_dir][acc_type] + offset_arm * acc_per_meter[acc_dir][acc_type]

        return acc * Transport.g

    @staticmethod
    def get_wind_pressure(hs):
        assert hs >= 0.0

        if hs <= 4:
            return 0.3
        elif hs <= 6:
            return 0.5
        else:
            return 1

    @staticmethod
    def get_criteria(hs):
        assert hs >= 0

        if hs <= 4:
            acc_waterline = {
                "ax": {"roll": 0.0, "quartering": 0.08, "pitch": 0.12},
                "ay": {"roll": 0.26, "quartering": 0.2, "pitch": 0.0},
                "az": {"roll": 0.15, "quartering": 0.12, "pitch": 0.08},
            }

            acc_per_meter = {
                "ax": {"roll": 0.0, "quartering": 0.003, "pitch": 0.004},
                "ay": {"roll": 0.017, "quartering": 0.013, "pitch": 0.0},
                "az": {"roll": 0.017, "quartering": 0.009, "pitch": 0.004},
            }
        elif hs <= 6:
            acc_waterline = {
                "ax": {"roll": 0.0, "quartering": 0.12, "pitch": 0.17},
                "ay": {"roll": 0.37, "quartering": 0.28, "pitch": 0.0},
                "az": {"roll": 0.2, "quartering": 0.15, "pitch": 0.1},
            }

            acc_per_meter = {
                "ax": {"roll": 0.0, "quartering": 0.004, "pitch": 0.006},
                "ay": {"roll": 0.017, "quartering": 0.013, "pitch": 0.0},
                "az": {"roll": 0.017, "quartering": 0.011, "pitch": 0.007},
            }
        else:
            acc_waterline = {
                "ax": {"roll": 0.0, "quartering": 0.15, "pitch": 0.25},
                "ay": {"roll": 0.5, "quartering": 0.4, "pitch": 0.0},
                "az": {"roll": 0.2, "quartering": 0.15, "pitch": 0.1},
            }

            acc_per_meter = {
                "ax": {"roll": 0.0, "quartering": 0.005, "pitch": 0.007},
                "ay": {"roll": 0.017, "quartering": 0.013, "pitch": 0.0},
                "az": {"roll": 0.017, "quartering": 0.012, "pitch": 0.007},
            }
        return acc_waterline, acc_per_meter
