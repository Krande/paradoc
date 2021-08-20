import numpy as np

from ..utils import roundoff


def vd(h_s, lift_from="supply vessel"):
    """
    V_D From EN13852-1:2013

    :equation: V_D = 6 * H_S / (H_S + 8)

    :param h_s: Significant Wave Height
    :param lift_from:

    :return:
    """
    if lift_from == "supply vessel":
        return 6 * h_s / (h_s + 8)
    else:
        raise NotImplementedError()


def kh(single_fall=True, rated_capacity=True):
    """
    K_H From EN13852-1:2013

    :param single_fall:
    :param rated_capacity:
    :return:
    """
    if rated_capacity is True and single_fall is True:
        return 0.5
    elif rated_capacity is True and single_fall is False:
        return 0.28
    elif rated_capacity is False and single_fall is True:
        return 0.65
    else:
        return 0.4


def vh(k_h, v_d, v_c):
    """
    :equation: V_H=K_H*sqrt(V_D**2+V_C**2)

    :param k_h: Velocity factor. Default=0.65
    :param v_d: Load supporting deck velocity
    :param v_c: Crane Boom tip velocity. Default=0 for bottom supported structure

    :return: V_H From EN13852-1:2013 [m/s]
    """
    return roundoff(k_h * np.sqrt(v_d ** 2 + v_c ** 2))


def vl(v_d, k_l=0.6, v_c=0):
    """


    :equation: V_L=K_L*sqrt(V_D**2+V_C**2)

    :param v_d: Load supporting deck velocity
    :param k_l: Velocity factor. Default = 0.6
    :param v_c: Crane Boom tip velocity. Default: 0 for bottom supported structure

    :return: V_L From EN13852-1:2013 [m/s]
    """

    return k_l * np.sqrt(v_d ** 2 + v_c ** 2)


def vr(h_s, k_r=0.25, v_c=0):
    """
    Radial velocity

    :equation: V_R = K_R * sqrt(V_D ** 2 + V_C ** 2)

    :param h_s: Significant Wave Height
    :param k_r: Velocity factor. Default = 0.25
    :param v_c: Crane Boom tip velocity. Default=0 for bottom supported structure

    :return: V_R From EN13852-1:2013 [m/s]
    """

    return k_r * np.sqrt(vd(h_s) ** 2 + v_c ** 2)


def hoist_v(h_s, v_c=0, single_fall=True, rated_capacity=True):
    """

    :param h_s: Significant Wave Height
    :param v_c: Crane Boom tip velocity. Default = 0 for bottom supported structure
    :param single_fall: True if wire is arranged for single fall
    :param rated_capacity: True if crane is lifting for rated capacity or no hook load.

    :return:
    """
    return vh(kh(single_fall, rated_capacity), vd(h_s), v_c)


def slew_v(h_s, d_o, k_l=0.6, v_c=0):
    """
    Converts V_L (From EN13852-1:2013) lateral boom tip velocity to rotational velocity in radian per second.

    :equation: omega = V_L / D_o

    :param h_s: Significant Wave Height
    :param d_o: Outreach Distance
    :param k_l: Lateral velocity factor. Default = 0.6
    :param v_c: Crane Boom tip velocity. Default = 0 for bottom supported structure

    :return: radian per second
    """

    return roundoff(vl(h_s, k_l, v_c) / d_o)
