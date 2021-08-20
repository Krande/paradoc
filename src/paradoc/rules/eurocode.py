import json
import math
import os
from collections import OrderedDict

import numpy as np

from ..utils import roundoff


class Bolt(object):
    """
    Bolt calculations according to EN1993-1-8:2005

    Note! Units are defined by default in m, N, Pa. However, it is possible to change all default parameters.

    Note! This is a work in progress class!

    :param d: Bolt diameter
    :param d_0: Bolt hole diameter
    :param t: Plate thickness
    :param bolt_class: Default is 8.8 bolt. Alternative is 10.9 or manually set f_y, f_u parameters
    :param base_mat: Base material. Default is S420. Alternative is S355 or manually set f_yb, f_ub parameters
    :param end_bolt: Whether or not the bolt is an interior or end bolt
    :param tearing_dir: Bolt Tearing direction. Default is "force", alternative is "normal"
    :param shear_threaded: Whether or not shear through bolt is in threads or not. Default is True.
    :param bolt_cat: Bolt category (See table below)
    :param e_1: Distance to edge (see figure below)
    :param e_2: Distance to edge (see figure below)
    :param e_3: Distance to edge (see figure below)
    :param e_4: Distance to edge (see figure below)
    :param p_1: Distance between bolts (see table below)
    :param p_2: Distance between bolts (see table below)


    Bolt Categories (from Table 3.2 EN1993-1-8:2005)

        .. image:: /_static/rules/bolt_categories.png


    Distance to edge (from Figure 3.1 EN1993-1-8:2005)

        .. image:: /_static/rules/bolt_distances.png


    Distances between bolts (from Table 3.3 EN1993-1-8:2005)

        .. image:: /_static/rules/bolt_positions.png

    """

    def __init__(
        self,
        d,
        d_0,
        t,
        bolt_class="8.8",
        base_mat="S420",
        bolt_cat="A",
        end_bolt=True,
        tearing_dir="force",
        shear_threaded=True,
        countersunk=False,
        e_1=None,
        e_2=None,
        e_3=None,
        e_4=None,
        p_1=None,
        p_2=None,
    ):
        # Bolt scenario
        self.end_bolt = end_bolt
        self.tearing_dir = tearing_dir
        self.bolt_cat = bolt_cat
        self.shear_threaded = shear_threaded
        self.countersunk = countersunk

        # Bolt geometry
        self.e_1, self.e_2, self.e_3, self.e_4 = e_1, e_2, e_3, e_4
        self.p_1, self.p_2 = p_1, p_2
        self.d_0 = d_0
        self.d = d
        self.t = t

        # Bolt material
        self.bolt_class = bolt_class
        if bolt_class == "8.8":
            f_u, f_y = 800e6, 640e6
        elif bolt_class == "10.9":
            f_u, f_y = 800e6, 640e6
        else:
            print('Unknown Bolt class "{}". Will use values for type "8.8"'.format(bolt_class))
            f_u, f_y = 800e6, 640e6

        self.f_u = f_u
        self.f_y = f_y

        # Base material
        if base_mat == "S420":
            f_ub, f_yb = 520e6, 420e6
        elif base_mat == "S355":
            f_ub, f_yb = 510e6, 355e6
        else:
            print('Unknown Mat Grade "{}". Will use values for type "S420"'.format(bolt_class))
            f_ub, f_yb = 520e6, 420e6
        self.f_ub = f_ub
        self.f_yb = f_yb

        # Safety Factors
        self.g_m0 = 1.15
        self.g_m1 = 1.15
        self.g_m2 = 1.30

    @property
    def alpha_d(self):
        if self.tearing_dir == "force":
            if self.end_bolt is True:
                return self.e_1 / (3 * self.d_0)
            else:
                return self.p_1 / (3 * self.d_0) - 0.25

    @property
    def alpha_b(self):
        return min(self.alpha_d, self.f_ub / self.f_u, 1.0)

    @property
    def alpha_v(self):
        """

        :return:
        """
        if self.shear_threaded is True:
            if self.bolt_class in ["4.6", "5.6", "8.8"]:
                return 0.6
            elif self.bolt_class in ["4.8", "5.8", "6.8", "10.9"]:
                return 0.5
        else:
            return 0.6

    @property
    def k_1(self):
        """
        Calculations from table 3.4

        :return:
        """
        if self.end_bolt is True:
            return min(2.8 * self.e_2 / self.d_0 - 1.7, 1.4 * self.p_2 / self.d_0, 2.5)
        else:
            return min(1.4 * self.p_2 / self.d_0 - 1.7, 2.5)

    @property
    def k_2(self):
        if self.countersunk is True:
            return 0.63
        else:
            return 0.9

    @property
    def bearing_capacity(self):
        """
        F_b,Rd =

        :return:
        """
        return self.k_1 * self.alpha_b * self.f_ub * self.d * self.t / self.g_m2

    @property
    def distances_check(self):
        # TODO: Evaluate how to implement

        return None

    @property
    def A(self):
        """
        Gross cross section of the bolt

        A=pi*r**2

        """

        return roundoff(np.pi * (self.d / 2) ** 2)

    @property
    def As(self):
        r"""

        from ISO 898 Bolts Tensile Stress Area
        As,nom = (π / 4) ((d2 + d3)/ 2)2                        (2)

        where

        As,nom = nominal stress area (m, mm2)
        d2  = the basic pitch diameter of the external thread according ISO 724 ISO general-purpose metric screw
            threads -- Basic dimensions (m, mm)
        d3  = d1 - H / 6 = the minor diameter of external tread (m, mm)
        d1  = the basic minor diameter of external thread according ISO 724
        H   = the height of the fundamental triangle of the thread according ISO 68-1 ISO general purpose screw
            threads (m, mm)

        Note! Thread info is extracted from

        https://www.engineeringtoolbox.com/metric-threads-d_777.html
        """
        dir_path = os.path.dirname(os.path.realpath(__file__))

        with open(dir_path + r"\resources\bolts.json") as data_file:
            bolt_db = json.load(data_file, object_pairs_hook=OrderedDict)

        d_ = "M{:0d}".format(int(self.d * 1000))
        bolt_sizes = list(bolt_db["coarse"]["data"].keys())

        if d_ in bolt_sizes:
            return

        d_mm = 1000 * self.d
        for i, bolt_key in enumerate(bolt_sizes):

            bs = float(bolt_key.lower().replace("m", ""))
            if i == 0:
                if d_mm < bs:
                    print('Bolt data from {}: "{}"'.format(bolt_key, bolt_db["coarse"]["data"][bolt_key]))
            else:
                bs_prev_key = bolt_sizes[i - 1]
                bs_prev = float(bs_prev_key.lower().replace("m", ""))
                if bs_prev < d_mm < bs:
                    print('Bolt data from {}: "{}"'.format(bolt_key, bolt_db["coarse"]["data"][bolt_key]))
        # for bolt_size in
        # coarse =
        # d3 = d1 - H / 6
        # return (np.pi/4)*((d_2+d_3)/2)**2
        return None

    @property
    def shear_capacity(self):
        """
        F_v,Rd =

        """
        return self.alpha_v * self.f_ub * self.A / self.g_m2

    @property
    def tension_capacity(self):
        """
        F_t,Rd =
        """

        return self.k_2 * self.f_ub

    def __repr__(self):

        return """Parameters:
k_1: {}, alpha_d: {}, alpha_b: {}

Results:
F_bRd: {:.2f} kN (Bearing Capacity)
""".format(
            roundoff(self.k_1),
            roundoff(self.alpha_d),
            roundoff(self.alpha_b),
            roundoff(self.bearing_capacity / 1000),
        )


class BoltGroup(object):
    """
    TODO: Make a similar type of class for group of bolts..

    """

    def __init__(self):
        self.k1 = None


# region bolt functions


# endregion


class MemberCheck(object):
    """
    :param member_mat: Member material for code check
    :param member_prop: Contains information about the member properties, e.g. area, shear area, .. etc.
    :param sec_class: Member section class, 1 to 4. Default section class is 1
    :param check_type: EC3 check type, ULS, ALS, etc. Default is ALS

    Material properties should use SI units, i.e. meter, seconds, Joule, etc.
    """

    def __init__(self, member_mat, member_prop, sec_class=1, check_type="ALS"):
        # Member scenario
        self._sec_class = sec_class
        self._check_type = check_type

        # Member geometry
        # This info should be stored on the member, not in the member check class
        self._member_prop = member_prop

        # Member material
        # Maybe inherent material properties?
        # Yield strength is extracted as: self.member_mat.f_y,
        # material density as: self.member_mat.density,
        # and thus need object member_mat to have this structure
        self._member_mat = member_mat

        # Partial Factors, standard is EC3 base value
        self._g_m0 = 1.0
        self._g_m1 = 1.0
        self._g_m2 = 1.25

    #     # Check of 'RF1', ... , 'RM3'. Make smart to understand if it is e.g. shear or axial forces
    #     # Control for explicit force components

    def perform_check(self, design_value, force_comp):
        """
        TODO: Have to generalize this check algorithm based on model orientation and force direction.
        """
        if "RF" in force_comp:
            if "2" in force_comp:
                if design_value < 0:
                    return self.compression_resistance, self.cap_utilization(design_value, self.compression_resistance)
                else:
                    return self.tension_resistance, self.cap_utilization(design_value, self.tension_resistance)
            else:
                return self.shear_resistance, self.cap_utilization(design_value, self.shear_resistance)
        elif "RM" in force_comp:
            if "2" in force_comp:
                return 1.0, 1.0
            else:
                return self.bending_moment_resistance, self.cap_utilization(
                    design_value, self.bending_moment_resistance
                )
        else:
            raise Exception("Unknown force component {}".format(force_comp))

    def cap_utilization(self, design_value, resistance):
        return design_value / resistance

    @property
    def shear_resistance(self):
        return (self.member_prop.shear_area * (self.member_mat.f_y / math.sqrt(3))) / self.g_m0

    @property
    def tension_resistance(self):
        return (self.member_prop.area * self.member_mat.f_y) / self.g_m0

    @property
    def compression_resistance(self):
        if self.sec_class < 4:
            return (self.member_prop.area * self.member_mat.f_y) / self.g_m0
        else:
            return (self.member_prop.area_eff * self.member_mat.f_y) / self.g_m0

    @property
    def bending_moment_resistance(self):
        return (self.member_prop.W_pl_y * self.member_mat.f_y) / self.g_m0

    @property
    def sec_class(self):
        return self._sec_class

    @property
    def member_prop(self):
        return self._member_prop

    @property
    def member_mat(self):
        return self._member_mat

    @property
    def check_type(self):
        if self._check_type == "ALS":
            self._g_m0 = 1.00
            self._g_m1 = 1.00
            self._g_m2 = 1.30
        elif self._check_type == "ULS":
            self._g_m0 = 1.15
            self._g_m1 = 1.15
            self._g_m2 = 1.30
        else:
            raise Exception("Unknown code check type. ALS or ULS?")
        return self._check_type

    @property
    def g_m0(self):
        return self._g_m0

    @property
    def g_m1(self):
        return self._g_m1

    @property
    def g_m2(self):
        return self._g_m2
