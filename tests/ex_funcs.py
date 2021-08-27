def my_calc_example_1(a, b):
    """A calculation with doc stub"""
    V_x = a + 1 * (0.3 + a * b) ** 2
    return V_x


def my_calc_example_2(a, b):
    """
    A calculation with a longer doc stub
    """
    V_n = a + 1 * (0.16 + a * b) ** 2
    V_x = V_n * 0.98
    return V_x
