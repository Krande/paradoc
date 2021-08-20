from paradoc.utils import roundoff


def local_yield_check(eps_crg, t, l):
    """

    :param eps_crg: \\epsilon_{crl}
    :param t: Thickness of element
    :param l: Length of element

    :eq: $$\\epsilon_{crl} <= \\epsilon_{crg}*(1+\\frac{5*t}{3*l})$$ :/eq:

    :return: Max

    """

    return roundoff(eps_crg * (1 + (5 * t) / (3 * l)))
